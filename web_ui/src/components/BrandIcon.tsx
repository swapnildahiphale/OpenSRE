import React from 'react';
import * as SimpleIcons from 'simple-icons';
import { clsx } from 'clsx';
import Image from 'next/image';

type BrandIconProps = {
    slug: string;
    size?: number;
    className?: string;
    color?: string; // Override brand color
};

// Map slugs to local files in public/icons
const LOCAL_OVERRIDES: Record<string, string> = {
    'amazonaws': '/icons/aws.png',
    'aws': '/icons/aws.png',
    'microsoftazure': '/icons/azure.png',
    'azure': '/icons/azure.png',
    'servicenow': '/icons/servicenow.webp',
    'splunk': '/icons/splunk.png',
    'slack': '/icons/slack.png',
    'googlecloud': '/icons/gcp.jpg', // New addition
    'gcp': '/icons/gcp.jpg'          // New addition
};

export const BrandIcon = ({ slug, size = 24, className, color }: BrandIconProps) => {
    const normalize = (s: string) => {
        return s.toLowerCase().replace(/[^a-z0-9]/g, '');
    };

    const target = normalize(slug);
    
    // 1. Check for Local Override (User provided images)
    const localImage = LOCAL_OVERRIDES[slug] || LOCAL_OVERRIDES[target];

    if (localImage) {
        return (
            <div className={clsx("relative flex items-center justify-center", className)} style={{ width: size, height: size }}>
                <Image 
                    src={localImage} 
                    alt={slug} 
                    width={size} 
                    height={size} 
                    className="object-contain"
                />
            </div>
        );
    }

    // 2. Dynamic lookup from simple-icons
    let iconKey = Object.keys(SimpleIcons).find(key => {
        if (key === 'default' || key === '__esModule') return false;
        const i = (SimpleIcons as any)[key];
        return i && (normalize(i.slug) === target || normalize(i.title) === target);
    });

    const icon = iconKey ? (SimpleIcons as any)[iconKey] : null;

    // Fallback text if icon not found
    if (!icon) {
        return (
            <div className={clsx("flex items-center justify-center font-bold text-stone-400 text-[10px] uppercase", className)} style={{ width: size, height: size }}>
                {slug.substring(0, 3)}
            </div>
        ); 
    }

    return (
        <svg
            role="img"
            viewBox="0 0 24 24"
            width={size}
            height={size}
            className={className}
            fill={color || `#${icon.hex}`}
            xmlns="http://www.w3.org/2000/svg"
            style={{ minWidth: size, minHeight: size }}
        >
            <title>{icon.title}</title>
            <path d={icon.path} />
        </svg>
    );
};
