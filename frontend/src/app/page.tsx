import { AuthGate } from "@/components/AuthGate";
import { Dashboard } from "@/components/Dashboard";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <AuthGate>
      <Dashboard />
      <Footer />
    </AuthGate>
  );
}
