import { Users, Activity, CreditCard, Bot, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

const stats = [
  { name: "API Calls", value: "0 / 1,000", icon: Activity, color: "text-blue-500", bg: "bg-blue-500/10" },
  { name: "AI Tokens", value: "0 / 100,000", icon: Bot, color: "text-purple-500", bg: "bg-purple-500/10" },
  { name: "Team Members", value: "1", icon: Users, color: "text-green-500", bg: "bg-green-500/10" },
  { name: "Current Period Cost", value: "₹0.00", icon: CreditCard, color: "text-orange-500", bg: "bg-orange-500/10" },
];

const recentActivity = [
  { id: "1", action: "Account created", time: "Just now", type: "info" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of your AI API usage and billing</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="rounded-lg border bg-card p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">{stat.name}</p>
                <p className="mt-1 text-2xl font-bold">{stat.value}</p>
              </div>
              <div className={cn("p-3 rounded-full", stat.bg)}>
                <stat.icon className={cn("h-6 w-6", stat.color)} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-card">
        <div className="border-b p-4">
          <h2 className="text-lg font-semibold">Recent Activity</h2>
        </div>
        <div className="p-4">
          {recentActivity.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <TrendingUp className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-4">No activity yet</p>
              <p className="text-sm">Start making API calls to see activity here</p>
            </div>
          ) : (
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-full bg-primary/10">
                      <Activity className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">{activity.action}</p>
                      <p className="text-sm text-muted-foreground">{activity.time}</p>
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground">{activity.type}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}