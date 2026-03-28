import { ChatMessage } from '@/types/chat';

export const fullSimulationSequence: ChatMessage[] = [
    {
        id: 'msg-2',
        type: 'agent_thought',
        sender: 'Payment Bot',
        timestamp: '10:15 PM',
        content: 'Analyzing alert context for `payment-gateway-api` in `c1-useast1-prod-04`...'
    },
    {
        id: 'msg-3',
        type: 'tool_step',
        sender: 'Payment Bot',
        timestamp: '10:15 PM',
        content: 'Analyze Application Performance (New Relic)',
        toolCall: {
            id: 'tc-1',
            toolName: 'Analyze APM Trace',
            toolIcon: 'newrelic',
            command: "newrelic.apm.get_transaction_trace(app='payment-gateway-api', window='15m')",
            status: 'completed',
            result: "Avg Response Time: 5,200ms (Baseline: 120ms)\nCritical Segment: 'FraudDecisionSidecar/evaluate' (Duration: 4.8s)\nError Rate: 0.5% (Normal)",
            duration: '1.2s'
        }
    },
    {
        id: 'msg-4',
        type: 'tool_step',
        sender: 'Payment Bot',
        timestamp: '10:15 PM',
        content: 'Diagnose Payment Sidecar (Learned Tool)',
        toolCall: {
            id: 'tc-2',
            toolName: 'Diagnose Payment Sidecar',
            toolIcon: 'learned-tool', // Special icon trigger
            command: "k8s.check_resources(namespace='payments-prod', container='fraud-sidecar')",
            status: 'completed',
            result: "[DIAGNOSIS] High Risk\nContainer: fraud-sidecar\nMemory Usage: 255MB / 256MB (99.6%)\nRestart Count: 12 (CrashLoopBackOff)\nLast Exit: OOMKilled (137)",
            duration: '0.5s'
        }
    },
    {
        id: 'msg-5',
        type: 'tool_step',
        sender: 'Payment Bot',
        timestamp: '10:16 PM',
        content: 'Correlate Changes & Logs (Jenkins + Splunk)',
        toolCall: {
            id: 'tc-3',
            toolName: 'Correlate Deployments',
            toolIcon: 'jenkins',
            command: "jenkins.get_build_info(job='payment-gateway-config') + splunk.query(index='payments')",
            status: 'completed',
            result: "[RESULT: Jenkins]\nBuild #892 (merged 15 mins ago)\nAuthor: s.engineer@capitalone.com\nCommit: 'chore: optimize sidecar resources (request 1G -> 256M)'\n\n[RESULT: Splunk]\nLog: 'java.lang.OutOfMemoryError: Java heap space' in fraud-sidecar",
            duration: '2.1s'
        }
    },
    {
        id: 'msg-6',
        type: 'conclusion',
        sender: 'Payment Bot',
        timestamp: '10:16 PM',
        content: "**Root Cause Identified:** `OOMKilled` crash loop in `fraud-sidecar` caused by recent resource reduction in Build #892.\n\n**Recommended Action:** Revert config change immediately.",
        metadata: {
            confidence: 99,
            policy: 'c1_critical_payments_response_v3',
            memoryId: 'mem-sidecar',
            memoryContent: 'Heuristic: Fraud Sidecar requires min 512MB Heap.',
            actions: [
                { label: 'Revert Build #892', action: 'revert_build', icon: 'rotate-ccw' },
                { label: 'View in New Relic', action: 'view_nr', icon: 'external-link' },
                { label: 'View Jenkins Log', action: 'view_jenkins', icon: 'file-text' }
            ]
        }
    }
];

export const resolutionSequence: ChatMessage[] = [
    {
        id: 'msg-7',
        type: 'user_message',
        sender: 'User',
        timestamp: '10:17 PM',
        content: 'Go ahead, fix it.'
    },
    {
        id: 'msg-8',
        type: 'agent_thought',
        sender: 'Payment Bot',
        timestamp: '10:17 PM',
        content: 'Initiating revert of Build #892 via Jenkins...'
    },
    {
        id: 'msg-9',
        type: 'tool_step',
        sender: 'Payment Bot',
        timestamp: '10:17 PM',
        content: 'Revert Configuration',
        toolCall: {
            id: 'tc-4',
            toolName: 'Jenkins Revert Job',
            toolIcon: 'jenkins',
            command: "jenkins.build('payment-gateway-config-revert', parameters={ 'BUILD_ID': 892 })",
            status: 'completed',
            result: "Build #893 started.\nStatus: SUCCESS\nConfig restored to previous version (Build #891).",
            duration: '4.5s'
        }
    },
    {
        id: 'msg-10',
        type: 'agent_thought',
        sender: 'Payment Bot',
        timestamp: '10:17 PM',
        content: 'Monitoring service recovery. Pods stabilizing...'
    },
    {
        id: 'msg-11',
        type: 'conclusion',
        sender: 'Payment Bot',
        timestamp: '10:18 PM',
        content: "**Incident Resolved.**\n\nService `payment-gateway-api` latency has returned to baseline (120ms). Pods are healthy.\n\nClosing PagerDuty incident.",
        metadata: {
            confidence: 100,
            policy: 'auto_resolve',
            actions: []
        }
    }
];
