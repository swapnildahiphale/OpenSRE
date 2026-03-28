'use client';

import React from 'react';
import { clsx } from 'clsx';
import { Bot, RotateCcw, ExternalLink, FileText, ShieldCheck, BrainCircuit } from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import { Logo } from '@/components/Logo';

function escapeHtml(str: string): string {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

export function MessageBubble({ message }: { message: ChatMessage }) {
    const isAgent = message.type === 'agent_thought' || message.type === 'conclusion';
    const isConclusion = message.type === 'conclusion';
    const isUser = message.sender === 'User';

    return (
        <div className={clsx("mb-6", isUser ? "flex justify-end" : "")}>
            <div className={clsx("flex gap-3 max-w-3xl", isUser ? "flex-row-reverse" : "")}>
                {/* Avatar */}
                <div className="flex-shrink-0 mt-1">
                    {isAgent ? (
                        <div className="w-8 h-8 rounded-lg bg-stone-100 dark:bg-stone-700 flex items-center justify-center border border-stone-200 dark:border-stone-600">
                            <Logo className="w-5 h-5" />
                        </div>
                    ) : (
                        <div className="w-8 h-8 rounded-lg bg-stone-200 dark:bg-stone-700 flex items-center justify-center text-xs font-bold text-stone-600 dark:text-stone-300">
                            {message.sender.substring(0, 2).toUpperCase()}
                        </div>
                    )}
                </div>

                <div className="flex-1">
                    <div className={clsx("flex items-center gap-2 mb-1", isUser ? "justify-end" : "")}>
                        <span className="text-sm font-bold text-stone-900 dark:text-white">{message.sender}</span>
                        {isAgent && <span className="text-xs text-stone-600 bg-stone-100 dark:bg-stone-700 px-1.5 py-0.5 rounded uppercase font-bold">Bot</span>}
                        <span className="text-xs text-stone-500">{message.timestamp}</span>
                    </div>

                    {isConclusion ? (
                        <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-lg p-4 shadow-sm">
                            <div className="flex items-center gap-2 mb-3 text-green-600 dark:text-green-400">
                                <ShieldCheck className="w-5 h-5" />
                                <span className="font-bold text-sm uppercase tracking-wide">Investigation Complete</span>
                                <span className="ml-auto text-xs text-stone-400 font-mono">Confidence: {message.metadata?.confidence}%</span>
                            </div>
                            <div className="prose dark:prose-invert prose-sm max-w-none mb-4">
                                {/* Simple markdown parser replacement for demo */}
                                {message.content?.split('\n').map((line, i) => (
                                    <p key={i} className="mb-1" dangerouslySetInnerHTML={{
                                        __html: escapeHtml(line).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/`(.*?)`/g, '<code class="bg-stone-100 dark:bg-stone-700 px-1 rounded">$1</code>')
                                    }} />
                                ))}
                            </div>

                            {/* Memory Recall Chip */}
                            {message.metadata?.memoryContent && (
                                <div className="flex items-center gap-2 mb-4 p-2 bg-stone-50 dark:bg-stone-800 border border-stone-200 dark:border-stone-600 rounded-md text-xs text-stone-700 dark:text-stone-300">
                                    <BrainCircuit className="w-3 h-3" />
                                    <span className="font-semibold">Recalled:</span>
                                    <span>{message.metadata.memoryContent}</span>
                                </div>
                            )}

                            {message.metadata?.actions && (
                                <div className="flex flex-wrap gap-2">
                                    {message.metadata.actions.map((action: any, idx: number) => (
                                        <button 
                                            key={idx}
                                            className={clsx(
                                                "flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors border",
                                                idx === 0 
                                                    ? "bg-green-600 text-white border-green-600 hover:bg-green-700 shadow-sm"
                                                    : "bg-white dark:bg-stone-700 text-stone-700 dark:text-stone-300 border-stone-200 dark:border-stone-600 hover:bg-stone-50 dark:hover:bg-stone-700"
                                            )}
                                        >
                                            {action.icon === 'rotate-ccw' && <RotateCcw className="w-4 h-4 mr-2" />}
                                            {action.icon === 'external-link' && <ExternalLink className="w-4 h-4 mr-2" />}
                                            {action.icon === 'file-text' && <FileText className="w-4 h-4 mr-2" />}
                                            {action.label}
                                        </button>
                                    ))}
                                </div>
                            )}
                            
                            <div className="mt-3 pt-3 border-t border-stone-100 dark:border-stone-700 text-xs text-stone-400 flex items-center gap-2">
                                <span>Policy:</span>
                                <code className="bg-stone-100 dark:bg-stone-700 px-1.5 py-0.5 rounded text-stone-600 dark:text-stone-400">
                                    {message.metadata?.policy}
                                </code>
                            </div>
                        </div>
                    ) : (
                        <div className="text-stone-800 dark:text-stone-200 text-sm leading-relaxed">
                            {message.content}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
