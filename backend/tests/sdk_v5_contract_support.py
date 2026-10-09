from dataclasses import fields, MISSING, is_dataclass
from enum import Enum
import inspect
import json
from pathlib import Path
import types
from typing import get_type_hints, get_origin, get_args, Annotated, Literal, Union
from opensprite_backend.agent import plugin as sdk

def annotation(t):
    origin = get_origin(t)
    args = get_args(t)
    if origin is Annotated: return annotation(args[0])
    if origin is Literal: return "Literal[" + ",".join(json.dumps(a) for a in args) + "]"
    if origin in (types.UnionType, Union): return " | ".join(annotation(a) for a in args)
    if origin: return origin.__name__ + "[" + ",".join(annotation(a) for a in args) + "]"
    if t is type(None): return "None"
    if t is Ellipsis: return "..."
    return getattr(t, "__name__", str(t))
def default(value):
    if value is MISSING or value is inspect.Parameter.empty: return {"required": True}
    if isinstance(value, Enum): return {"enum": type(value).__name__, "value": value.value}
    if is_dataclass(value): return {"dataclass": type(value).__name__, "fields": {f.name: default(getattr(value,f.name)) for f in fields(value)}}
    if isinstance(value, tuple): return list(value)
    return value
def contract():
    names = ("ExecutionLimits", "ModelLimits", "RunContext", "ContextReadRequest", "ContextSnapshot", "InputSource", "SummarySource", "StepRequest", "StepResult", "SummaryWriteRequest", "FinalOutput", "RunResult", "Message", "ConversationCompaction", "PublicRunError", "ModelMessage")
    records = {}
    for name in names:
        cls = getattr(sdk,name); hints=get_type_hints(cls)
        records[name] = {"frozen":cls.__dataclass_params__.frozen, "slots":list(cls.__slots__), "fields":[{"name":f.name,"type":annotation(hints[f.name]),"default":default(f.default)} for f in fields(cls)]}
    methods = {}
    for protocol, names in ((sdk.ExecutionHost,("run","checkpoint","read_context","estimate_input","infer","save_summary","finish")),(sdk.AgentLoopPlugin,("execute",)),(sdk.AgentLoopPluginFactory,("create",))):
        items={}
        for name in names:
            method=getattr(protocol,name); property_=isinstance(method,property); method=method.fget if property_ else method
            hints=get_type_hints(method); signature=inspect.signature(method)
            items[name] = {"property":property_, "async":inspect.iscoroutinefunction(method), "parameters":[{"name":p.name,"kind":p.kind.name,"type":annotation(hints[p.name]) if p.name in hints else None,"default":default(p.default)} for p in signature.parameters.values()],"return":annotation(hints['return'])}
        methods[protocol.__name__] = items
    return {"apiVersion":5,"entryPoint":"opensprite_backend.agent_loops.v5","records":records,"enums":{name:{v.name:v.value for v in getattr(sdk,name)} for name in ("CompletionReason","ModelFinishReason")},"protocols":methods}
