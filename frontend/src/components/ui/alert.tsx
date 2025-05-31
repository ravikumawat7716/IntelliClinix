import React from "react";
import { cn } from "@/lib/utils";

interface AlertProps {
  children: React.ReactNode;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({ children, className }) => {
  return (
    <div className={cn("p-4 border rounded-lg bg-yellow-100 text-yellow-800", className)}>
      {children}
    </div>
  );
};

interface AlertDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

export const AlertDescription: React.FC<AlertDescriptionProps> = ({ children, className }) => {
  return <p className={cn("text-sm", className)}>{children}</p>;
};
