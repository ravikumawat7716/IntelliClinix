import { cn } from '@/lib/utils';

export function Button({ className, ...props }) {
  return (
    <button
      className={cn(
        'px-4 py-2 rounded-xl text-white font-medium bg-blue-500 hover:bg-blue-600 transition',
        className
      )}
      {...props}
    />
  );
}

export default Button;