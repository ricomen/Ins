import { Toaster } from "sonner";

import { AppRouter } from "@/app/router/AppRouter";

export function App() {
  return (
    <>
      <AppRouter />
      <Toaster richColors position="top-right" closeButton />
    </>
  );
}
