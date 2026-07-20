import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ConversationComposer from './ConversationComposer';

describe('ConversationComposer message queue', () => {
  it('keeps input enabled while busy', () => {
    render(
      <ConversationComposer
        busy
        onSend={vi.fn()}
        onQueueMessage={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    const input = screen.getByTestId('conversation-composer-input');
    expect(input).toBeEnabled();
    expect(input).toHaveAttribute('placeholder', 'Queue a message…');
  });

  it('shows queued messages with Queued tag', () => {
    render(
      <ConversationComposer
        busy
        queuedMessages={['make it blue not green']}
        onSend={vi.fn()}
        onQueueMessage={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    const list = screen.getByTestId('conversation-composer-queued-list');
    expect(list).toHaveTextContent('make it blue not green');
    expect(list).toHaveTextContent('Queued');
    expect(list).not.toHaveTextContent('message queued');
  });

  it('lists each queued message separately', () => {
    render(
      <ConversationComposer
        busy
        queuedMessages={['check Redis', 'ignore payment']}
        onSend={vi.fn()}
        onQueueMessage={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    const items = screen.getAllByTestId('conversation-composer-queued-item');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('check Redis');
    expect(items[1]).toHaveTextContent('ignore payment');
    expect(screen.getAllByText('Queued')).toHaveLength(2);
  });

  it('calls onQueueMessage when submitting while busy', () => {
    const onQueueMessage = vi.fn();
    render(
      <ConversationComposer
        busy
        onSend={vi.fn()}
        onQueueMessage={onQueueMessage}
        onStop={vi.fn()}
      />,
    );

    const input = screen.getByTestId('conversation-composer-input');
    fireEvent.change(input, { target: { value: 'check logs next' } });
    fireEvent.click(screen.getByTestId('conversation-composer-send'));

    expect(onQueueMessage).toHaveBeenCalledWith('check logs next');
  });

  it('clears input after successful queue', async () => {
    const onQueueMessage = vi.fn().mockResolvedValue(undefined);
    render(
      <ConversationComposer
        busy
        onSend={vi.fn()}
        onQueueMessage={onQueueMessage}
        onStop={vi.fn()}
      />,
    );

    const input = screen.getByTestId('conversation-composer-input');
    fireEvent.change(input, { target: { value: 'check logs next' } });
    fireEvent.click(screen.getByTestId('conversation-composer-send'));

    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });

  it('keeps input and shows error when queue fails', async () => {
    const onQueueMessage = vi.fn().mockRejectedValue(new Error('Queue failed'));
    render(
      <ConversationComposer
        busy
        onSend={vi.fn()}
        onQueueMessage={onQueueMessage}
        onStop={vi.fn()}
      />,
    );

    const input = screen.getByTestId('conversation-composer-input');
    fireEvent.change(input, { target: { value: 'still here' } });
    fireEvent.click(screen.getByTestId('conversation-composer-send'));

    await waitFor(() => {
      expect(screen.getByTestId('conversation-composer-queue-error')).toHaveTextContent(
        'Queue failed',
      );
    });
    expect(input).toHaveValue('still here');
  });
});
