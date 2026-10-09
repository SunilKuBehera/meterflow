import { User, Shield, Bell, Key, Trash2 } from "lucide-react";

type FieldConfig =
  | { label: string; type: "text" | "email" | "password"; placeholder?: string; disabled?: boolean }
  | { label: string; type: "checkbox"; checked: boolean };

type ActionConfig = {
  label: string;
  variant?: "primary" | "destructive" | "secondary";
};

type SectionConfig = {
  title: string;
  icon: React.ElementType;
  fields?: FieldConfig[];
  actions?: ActionConfig[];
  description?: string;
  emptyState?: string;
};

const settingsSections: SectionConfig[] = [
  {
    title: "Profile",
    icon: User,
    fields: [
      { label: "Full Name", type: "text", placeholder: "John Doe" },
      { label: "Email", type: "email", placeholder: "john@example.com", disabled: true },
    ],
  },
  {
    title: "Security",
    icon: Shield,
    fields: [
      { label: "Current Password", type: "password" },
      { label: "New Password", type: "password" },
      { label: "Confirm New Password", type: "password" },
    ],
    actions: [
      { label: "Update Password", variant: "primary" },
    ],
  },
  {
    title: "Notifications",
    icon: Bell,
    fields: [
      { label: "Email Notifications", type: "checkbox", checked: true },
      { label: "Usage Alerts (80% quota)", type: "checkbox", checked: true },
      { label: "Usage Alerts (100% quota)", type: "checkbox", checked: true },
      { label: "Billing Receipts", type: "checkbox", checked: true },
    ],
  },
  {
    title: "API Keys",
    icon: Key,
    description: "Manage your API keys for programmatic access",
    actions: [
      { label: "Create New Key", variant: "primary" },
    ],
    emptyState: "No API keys created yet",
  },
  {
    title: "Danger Zone",
    icon: Trash2,
    description: "Irreversible actions",
    actions: [
      { label: "Delete Account", variant: "destructive" },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account and preferences</p>
      </div>

      {settingsSections.map((section) => (
        <div key={section.title} className="rounded-lg border bg-card">
          <div className="border-b p-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <section.icon className="h-5 w-5" />
              {section.title}
            </h2>
            {section.description && (
              <p className="mt-1 text-sm text-muted-foreground">{section.description}</p>
            )}
          </div>
          <div className="p-4 space-y-4">
            {section.fields?.map((field, i) => (
              <div key={i} className="space-y-1">
                <label className="block text-sm font-medium">{field.label}</label>
                {field.type === "checkbox" ? (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      defaultChecked={field.checked}
                      className="rounded border-input"
                    />
                    <span className="text-sm">{field.label}</span>
                  </label>
                ) : (
                  <input
                    type={field.type}
                    placeholder={field.placeholder}
                    disabled={field.disabled}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-ring"
                  />
                )}
              </div>
            ))}
            {section.actions?.map((action, i) => (
              <button
                key={i}
                className={cn(
                  "w-full rounded-md px-4 py-2 text-sm font-medium transition-colors",
                  action.variant === "primary"
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : action.variant === "destructive"
                    ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                )}
              >
                {action.label}
              </button>
            ))}
            {section.emptyState && !section.fields && (
              <p className="text-center text-muted-foreground py-4">{section.emptyState}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}