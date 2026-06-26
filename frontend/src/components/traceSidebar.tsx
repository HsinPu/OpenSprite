import { type PointerEvent } from "react";
import { CloseOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { RunInspector, type RunInspectorClient } from "./runInspector";

type TraceSidebarClient = RunInspectorClient & {
  traceInspectorCollapsed: { value: boolean };
  toggleTraceInspectorCollapsed: () => void;
};

export function TraceSidebar({
  client,
  beginTraceResize,
}: {
  client: TraceSidebarClient;
  beginTraceResize: (event: PointerEvent) => void;
}) {
  const copy = client.copy.value;
  const collapsed = client.traceInspectorCollapsed.value;

  return (
    <aside className="trace-sidebar" data-collapsed={collapsed} aria-label="Run trace inspector">
      {!collapsed ? (
        <>
          <Button
            className="trace-sidebar__resize"
            type="text"
            aria-label="Resize trace inspector"
            title="Drag to resize trace inspector"
            onPointerDown={beginTraceResize}
          />
          <div className="trace-sidebar__rail">
            <Button
              className="trace-sidebar__toggle"
              aria-expanded={!collapsed}
              aria-label="Close trace panel"
              title="Close trace panel"
              icon={<CloseOutlined />}
              onClick={client.toggleTraceInspectorCollapsed}
            >
              {copy.trace.collapse}
            </Button>
          </div>
          <RunInspector client={client} />
        </>
      ) : null}
    </aside>
  );
}
