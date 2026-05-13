import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
  bordered?: boolean;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ hoverable = false, bordered = true, className, children, ...props }, ref) => {
    const baseStyles = 'rounded-lg bg-white';
    const borderStyles = bordered ? 'border border-gray-200' : 'shadow-sm';
    const hoverStyles = hoverable ? 'hover:shadow-lg cursor-pointer transition-shadow duration-200' : 'shadow-md';

    return (
      <div
        ref={ref}
        className={`${baseStyles} ${borderStyles} ${hoverStyles} ${className || ''}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export const CardHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={`px-6 py-4 border-b border-gray-200 ${className || ''}`} {...props}>
    {children}
  </div>
);

export const CardContent = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={`px-6 py-4 ${className || ''}`} {...props}>
    {children}
  </div>
);

export const CardFooter = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={`px-6 py-4 border-t border-gray-200 flex justify-end gap-2 ${className || ''}`} {...props}>
    {children}
  </div>
);
