import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="font-semibold text-xl">
            MeterFlow
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/login" className="text-sm font-medium transition-colors hover:text-muted-foreground">
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      <section className="flex-1 flex items-center justify-center px-4 py-20">
        <div className="max-w-3xl text-center">
          <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-6xl">
            Meter, Bill, and Scale Your{" "}
            <span className="text-primary">AI API Usage</span>
          </h1>
          <p className="mb-8 text-lg text-muted-foreground max-w-2xl mx-auto">
            Multi-tenant SaaS for AI/API usage metering, quota enforcement, pricing,
            and subscription billing. Built for correctness under concurrency.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/signup"
              className="rounded-md bg-primary px-8 py-3 text-base font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Start Free Trial
            </Link>
            <Link
              href="/login"
              className="rounded-md border border-input bg-background px-8 py-3 text-base font-medium transition-colors hover:bg-accent"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      <section className="border-t py-20 px-4">
        <div className="container mx-auto max-w-4xl">
          <h2 className="mb-12 text-center text-3xl font-bold">Built for Production</h2>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="rounded-lg border bg-card p-6">
              <h3 className="mb-2 text-lg font-semibold">Tenant Isolation</h3>
              <p className="text-muted-foreground">
                Row-level security and server-side authorization ensure tenants never
                access each other's data.
              </p>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <h3 className="mb-2 text-lg font-semibold">Idempotent Metering</h3>
              <p className="text-muted-foreground">
                Deduplication at the database level prevents double-billing on retries
                and duplicate webhooks.
              </p>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <h3 className="mb-2 text-lg font-semibold">Concurrent Quotas</h3>
              <p className="text-muted-foreground">
                Transaction-safe quota enforcement handles the last-unit edge case
                under concurrent load.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t py-8 px-4">
        <div className="container mx-auto flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-sm text-muted-foreground">
            © 2024 MeterFlow. Built with Next.js, FastAPI, and Supabase.
          </p>
        </div>
      </footer>
    </main>
  );
}