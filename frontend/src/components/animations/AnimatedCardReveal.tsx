import type { HTMLAttributes, ReactNode } from "react";

export function staggerCardDelay(index: number) {
  return Math.min(index * 0.08, 0.4);
}

interface AnimatedCardRevealProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  delay?: number;
  disabled?: boolean;
}

export function AnimatedCardReveal({
  children,
  delay: _delay = 0,
  disabled: _disabled = false,
  ...props
}: AnimatedCardRevealProps) {
  return <div {...props}>{children}</div>;
}
