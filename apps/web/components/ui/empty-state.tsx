import * as React from "react";

import { cn } from "@/lib/utils";

const EmptyState = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => {
  return <div ref={ref} className={cn("rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 p-8 text-center", className)} {...props} />;
});
EmptyState.displayName = "EmptyState";

const EmptyStateTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(({ className, ...props }, ref) => {
  return <h3 ref={ref} className={cn("text-base font-semibold text-slate-900", className)} {...props} />;
});
EmptyStateTitle.displayName = "EmptyStateTitle";

const EmptyStateBody = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({ className, ...props }, ref) => {
  return <p ref={ref} className={cn("mt-2 text-sm text-slate-500", className)} {...props} />;
});
EmptyStateBody.displayName = "EmptyStateBody";

export { EmptyState, EmptyStateBody, EmptyStateTitle };
