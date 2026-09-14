from dataclasses import replace
from uuid import uuid4
import json
import asyncio
import httpx
import pytest

from opensprite_backend.inference.openrouter import ChatCompletionsInferenceAdapter, _complete_response
from opensprite_backend.inference.models import ModelRequest, ModelMessage, ModelToolDefinition, ModelToolCall, ModelTextDelta
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.inference.gateway import ModelGatewayError
from opensprite_backend.tools.builtins.calculator import CalculatorTool
from opensprite_backend.tools.definition import ToolContext


@pytest.mark.anyio
@pytest.mark.parametrize('compatibility', [False, True])
async def test_tool_result_roundtrip_both_transports(compatibility):
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body['stream'] is (not compatibility)
        assert body['tool_choice'] == 'auto'
        second = len(requests) == 2
        if second:
            assert body['messages'][-1]['role'] == 'tool'
            assert body['messages'][-1]['tool_call_id'] == 'call_calc'
            assert body['messages'][-1]['content'] == '35676357'
        call = {'id':'call_calc','type':'function','function':{'name':'calculator','arguments':'{"expression":"7391 * 4827"}'}}
        message = {'role':'assistant','content':'35676357' if second else None}
        if not second: message['tool_calls'] = [call]
        finish = 'stop' if second else 'tool_calls'
        if compatibility:
            assert 'stream_options' not in body
            return httpx.Response(200,json={'choices':[{'index':0,'message':message,'finish_reason':finish}]})
        delta = {'content':message['content']} if second else {'tool_calls':[dict(call,index=0)]}
        data = {'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
        return httpx.Response(200,headers={'Content-Type':'text/event-stream'},content='data: '+json.dumps(data)+'\n\ndata: [DONE]\n\n')
    pid = str(uuid4())
    endpoint = ProviderEndpointSnapshot(pid,1,'openai_chat_completions','https://example.com/v1','none',non_streaming_tools=compatibility)
    request = ModelRequest(pid,'test','default',(ModelMessage('user','calculate'),),(ModelToolDefinition('calculator','Arithmetic',{'type':'object'}),),provider_endpoint=endpoint)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ChatCompletionsInferenceAdapter(client,endpoint.endpoint('chat/completions'),bearer_auth=False)
        first = [event async for event in adapter.stream(request,'')]
        call = next(event for event in first if isinstance(event,ModelToolCall))
        assert call.arguments == {'expression':'7391 * 4827'}
        tool_result = await CalculatorTool().invoke(call.arguments, ToolContext(str(uuid4()), str(uuid4()), asyncio.Event()))
        result = tool_result.content
        followup = replace(request,messages=(*request.messages,ModelMessage('assistant','',(call,)),ModelMessage('tool',result,tool_call_id=call.call_id,tool_name=call.name)))
        final = [event async for event in adapter.stream(followup,'')]
        assert any(isinstance(event,ModelTextDelta) and event.text == result for event in final)
    assert len(requests) == 2


def test_json_text_is_not_a_tool_call():
    events = _complete_response({'choices':[{'index':0,'message':{'role':'assistant','content':'{"name":"calculator","arguments":{}}'},'finish_reason':'stop'}]})
    assert not any(isinstance(event,ModelToolCall) for event in events)


def test_invalid_tool_response_rejected():
    with pytest.raises(ModelGatewayError):
        _complete_response({'choices':[{'index':0,'message':{'role':'assistant','tool_calls':[{'id':'x','type':'function','function':{'name':'calculator','arguments':'{}'}}]},'finish_reason':'stop'}]})
