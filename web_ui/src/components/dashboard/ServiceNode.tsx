import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Activity, Database, Globe, Lock, Server } from 'lucide-react';
import { clsx } from 'clsx';

const ServiceNode = ({ data, selected }: any) => {
  const Icon = {
    frontend: Globe,
    api: Server,
    auth: Lock,
    db: Database,
    service: Activity
  }[data.type as string] || Activity;

  return (
    <div className={clsx(
      "px-4 py-3 shadow-lg rounded-xl bg-white dark:bg-stone-800 border-2 transition-all min-w-[150px]",
      selected ? "border-forest ring-4 ring-forest/20" : "border-stone-200 dark:border-stone-600",
      data.status === 'error' && !selected && "border-clay animate-pulse",
      data.status === 'warning' && !selected && "border-yellow-500"
    )}>
      <div className="flex items-center gap-3">
        <div className={clsx(
          "w-8 h-8 rounded-full flex items-center justify-center",
          data.status === 'error' ? "bg-clay-light/15 text-clay" :
          data.status === 'warning' ? "bg-yellow-100 text-yellow-600" :
          "bg-stone-100 text-stone-600 dark:bg-stone-700 dark:text-stone-400"
        )}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <div className="text-xs font-bold text-stone-900 dark:text-white">{data.label}</div>
          <div className="text-[10px] text-stone-500">{data.requests} req/s</div>
        </div>
      </div>

      {/* Handles */}
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-stone-400" />
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-stone-400" />
    </div>
  );
};

export default memo(ServiceNode);

