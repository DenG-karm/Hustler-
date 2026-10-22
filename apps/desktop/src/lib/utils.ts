import { clsx, type ClassValue } from 'clsx'

/**
 * Type-safe className merger.
 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}
