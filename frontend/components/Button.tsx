import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';

type ButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary';
}>;

export function Button({ children, variant = 'primary', ...props }: ButtonProps) {
  return (
    <button className={`button ${variant === 'secondary' ? 'button-secondary' : ''}`} type="button" {...props}>
      {children}
    </button>
  );
}
