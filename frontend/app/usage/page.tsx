import { BarChart3 } from "lucide-react";

export default function UsagePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Usage</h1>
        <p className="text-muted-foreground mt-1">Detailed breakdown of your API and AI token usage</p>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <div className="text-center py-12">
          <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">Usage Analytics</h3>
          <p className="mt-2 text-muted-foreground">
            Charts and detailed usage history will appear here once you start making API calls.
          </p>
          <ul className="mt-6 text-left max-w-md mx-auto space-y-2 text-sm text-muted-foreground">
            <li>• API call volume over time</li>
            <li>• AI token consumption (input, output, cached, reasoning)</li>
            <li>• Usage by endpoint and model</li>
            <li>• Quota utilization percentage</li>
            <li>• Export to CSV</li>
          </ul>
        </div>
      </div>
    </div>
  );
}