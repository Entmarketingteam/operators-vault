import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30",
        secondary: "bg-[var(--secondary)] text-[var(--secondary-foreground)] border border-[var(--border)]",
        destructive: "bg-red-600/20 text-red-300 border border-red-500/30",
        outline: "border border-[var(--border)] text-[var(--foreground)]",
        podcast: "bg-violet-600/20 text-violet-300 border border-violet-500/30",
        newsletter: "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30",
        category: "bg-amber-600/20 text-amber-300 border border-amber-500/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
