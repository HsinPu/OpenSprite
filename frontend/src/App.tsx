import { OpenSpriteShell } from "./components/openSpriteShell";
import { AppProviders } from "./providers/appProviders";

export default function App() {
  return (
    <AppProviders>
      <OpenSpriteShell />
    </AppProviders>
  );
}
