import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../../lib/utils'

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-fg hover:bg-primary-hover active:opacity-90',
  secondary: 'bg-secondary text-secondary-fg hover:bg-secondary-hover active:opacity-90',
  outline: 'border border-border bg-transparent text-text-primary hover:bg-surface-hover active:bg-surface',
  ghost: 'bg-transparent text-text-secondary hover:bg-surface-hover hover:text-text-primary active:bg-surface',
  destructive: 'bg-destructive text-destructive-fg hover:bg-destructive-hover active:opacity-90',
}

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-sm py-xs text-xs rounded-sm gap-xs',
  md: 'px-md py-sm text-sm rounded-md gap-sm',
  lg: 'px-lg py-md text-base rounded-lg gap-md',
  icon: 'p-sm rounded-md aspect-square justify-center',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled = false,
      children,
      leftIcon,
      rightIcon,
      type = 'button',
      ...props
    },
    ref,
  ) => {
    const isDisabled = disabled || isLoading

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        aria-busy={isLoading}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-colors select-none',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
          'disabled:pointer-events-none disabled:opacity-50',
          variantStyles[variant],
          sizeStyles[size],
          className,
        )}
        {...props}
      >
        {isLoading ? (
          <svg
            className="animate-spin text-current"
            style={{ width: '1em', height: '1em' }}
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
            data-testid="button-spinner"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        ) : (
          leftIcon
        )}
        {children && <span>{children}</span>}
        {!isLoading && rightIcon}
      </button>
    )
  },
)

Button.displayName = 'Button'
