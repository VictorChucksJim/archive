import { RequireAuth } from "@/components/RequireAuth";
import { Sidebar } from "@/components/Sidebar";

export default function TrashLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex min-h-screen">
        <Sidebar />
        {children}
      </div>
    </RequireAuth>
  );
}
