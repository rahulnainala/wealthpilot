import * as React from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  title: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  subClassName?: string;
  icon?: React.ReactNode;
}

export function KpiCard({ title, value, sub, subClassName, icon }: Props) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle>{title}</CardTitle>
        {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      </CardHeader>
      <CardContent>
        <div className="text-xl font-semibold tabular-nums tracking-tight sm:text-2xl">
          {value}
        </div>
        {sub != null ? (
          <div className={cn("mt-1 text-xs", subClassName)}>{sub}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}
