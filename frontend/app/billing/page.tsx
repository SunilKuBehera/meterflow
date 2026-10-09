import { CreditCard, Shield, Crown, ArrowRight } from "lucide-react";
import Link from "next/link";

const plans = [
  {
    name: "Free",
    price: "₹0",
    period: "/month",
    description: "Perfect for getting started",
    features: [
      "1,000 API calls/month",
      "100,000 AI tokens/month",
      "Basic usage analytics",
      "Community support",
    ],
    cta: "Current Plan",
    disabled: true,
  },
  {
    name: "Pro",
    price: "₹999",
    period: "/month",
    description: "For growing teams and applications",
    features: [
      "100,000 API calls/month",
      "10,000,000 AI tokens/month",
      "Advanced analytics & export",
      "Priority email support",
      "Custom rate limits",
    ],
    cta: "Upgrade to Pro",
    disabled: false,
  },
];

export default function BillingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Billing</h1>
        <p className="text-muted-foreground mt-1">Manage your subscription and billing details</p>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Current Plan</h2>
            <p className="text-muted-foreground">Free Tier</p>
          </div>
          <span className="rounded-full bg-green-500/10 px-3 py-1 text-sm font-medium text-green-500">
            Active
          </span>
        </div>
      </div>

      <h2 className="text-xl font-semibold">Available Plans</h2>
      <div className="grid gap-6 md:grid-cols-2">
        {plans.map((plan) => (
          <div
            key={plan.name}
            className="relative rounded-lg border bg-card p-6 flex flex-col"
          >
            {plan.name === "Pro" && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-0.5 text-xs font-medium text-primary-foreground">
                Most Popular
              </div>
            )}
            <div className="mb-4">
              <h3 className="text-lg font-semibold">{plan.name}</h3>
              <p className="text-muted-foreground text-sm">{plan.description}</p>
            </div>
            <div className="mb-4">
              <span className="text-4xl font-bold">{plan.price}</span>
              <span className="text-muted-foreground">{plan.period}</span>
            </div>
            <ul className="flex-1 space-y-3 mb-6">
              {plan.features.map((feature, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <Shield className="h-4 w-4 text-green-500 flex-shrink-0" />
                  {feature}
                </li>
              ))}
            </ul>
            <Link
              href={plan.name === "Pro" ? "/billing/checkout" : "#"}
              className={cn(
                "w-full rounded-md px-4 py-2 text-sm font-medium text-center transition-colors",
                plan.disabled
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {plan.cta}
              {!plan.disabled && <ArrowRight className="ml-2 h-4 w-4" />}
            </Link>
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Billing History</h2>
        <div className="text-center py-8 text-muted-foreground">
          <CreditCard className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <p className="mt-4">No billing history yet</p>
          <p className="text-sm">Invoices and receipts will appear here</p>
        </div>
      </div>
    </div>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}