import { CloseOutlined, MenuUnfoldOutlined } from "@ant-design/icons";
import { Button } from "antd";

type AnyRecord = Record<string, any>;

type MobileNavClient = {
  copy: { value: AnyRecord };
  sidebarOpen: { value: boolean };
  toggleSidebar: () => void;
};

export function MobileNavControls({ client }: { client: MobileNavClient }) {
  const copy = client.copy.value;
  const sidebarOpen = client.sidebarOpen.value;

  return (
    <>
      <Button
        className="mobile-nav-toggle"
        aria-controls="sidebar"
        aria-expanded={sidebarOpen}
        icon={sidebarOpen ? <CloseOutlined /> : <MenuUnfoldOutlined />}
        onClick={client.toggleSidebar}
      >
        {sidebarOpen ? copy.timeline.collapse : copy.app.menu}
      </Button>
      {sidebarOpen ? (
        <Button className="mobile-nav-backdrop" type="text" aria-label="Close menu" onClick={client.toggleSidebar} />
      ) : null}
    </>
  );
}
