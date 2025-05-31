import { cn } from '@/lib/utils';

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        'w-full p-2 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400',
        className
      )}
      {...props}
    />
  );
}

export default Input;