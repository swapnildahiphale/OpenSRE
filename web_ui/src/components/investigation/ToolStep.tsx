'use client';

import React from 'react';
import { clsx } from 'clsx';
import { Terminal, CheckCircle2, Loader2, ChevronRight, Cpu } from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import { BrandIcon } from '@/components/BrandIcon';

export function ToolStep({ message }: { message: ChatMessage }) {
    if (!message.toolCall) return null;
    
    const { toolCall } = message;
    const isCompleted = toolCall.status === 'completed';
    
    // Check if this is our "Learned Tool"
    const isLearnedTool = toolCall.toolIcon === 'learned-tool';

    return (
        <div className="mb-6 ml-8 group">
            <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-stone-900 dark:text-white">
                    {message.content}
                </span>
                {isLearnedTool && (
                    <span className="text-[10px] bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300 px-1.5 py-0.5 rounded-full uppercase font-bold tracking-wide flex items-center gap-1">
                        <Cpu className="w-3 h-3" /> Learned Tool
                    </span>
                )}
            </div>

            <div className={clsx(
                "border rounded-lg overflow-hidden transition-colors",
                isLearnedTool
                    ? "bg-stone-50 dark:bg-stone-900/50 border-stone-300 dark:border-stone-600"
                    : "bg-stone-50 dark:bg-stone-900/50 border-stone-200 dark:border-stone-700"
            )}>
                {/* Command Bar */}
                <div className={clsx(
                    "flex items-center gap-2 px-3 py-2 border-b",
                    isLearnedTool
                        ? "bg-stone-100 dark:bg-stone-700 border-stone-300 dark:border-stone-600"
                        : "bg-stone-100 dark:bg-stone-700 border-stone-200 dark:border-stone-600"
                )}>
                    {isLearnedTool ? (
                        <div className="p-0.5 bg-stone-600 rounded text-white">
                            <Cpu className="w-3 h-3" />
                        </div>
                    ) : (
                        <BrandIcon slug={toolCall.toolIcon} size={14} />
                    )}
                    <code className={clsx(
                        "flex-1 font-mono text-xs truncate",
                        isLearnedTool ? "text-stone-800 dark:text-stone-200" : "text-stone-600 dark:text-stone-300"
                    )}>
                        {toolCall.command}
                    </code>
                    {isCompleted ? (
                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                    ) : (
                        <Loader2 className="w-4 h-4 text-stone-500 animate-spin" />
                    )}
                </div>

                {/* Result Output */}
                {isCompleted && toolCall.result && (
                    <div className="p-3 font-mono text-xs leading-relaxed text-stone-700 dark:text-stone-300 overflow-x-auto">
                        <pre className="whitespace-pre-wrap">{toolCall.result}</pre>
                    </div>
                )}
            </div>
        </div>
    );
}
