'use client';

import type React from 'react';

import { useEffect, useRef, useState } from 'react';
import {
  ArrowUp,
  Loader2,
  MessageSquare,
  Paperclip,
  Plus,
  Trash2,
} from 'lucide-react';

import { ChatMessage } from '@/components/chat-message';
import { ExamplePrompts } from '@/components/example-prompts';
import { FilePreview } from '@/components/file-preview';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import {
  PDFDocument,
  RetrieveDocumentsNodeUpdates,
} from '@/types/graphTypes';

const THREAD_STORAGE_KEY = 'pdf-chat-thread-id';

const getStoredThreadId = () => window.sessionStorage.getItem(THREAD_STORAGE_KEY);

const setStoredThreadId = (threadId: string) => {
  window.sessionStorage.setItem(THREAD_STORAGE_KEY, threadId);
};

const clearStoredThreadId = () => {
  window.sessionStorage.removeItem(THREAD_STORAGE_KEY);
};

type Message = {
  role: 'user' | 'assistant';
  content: string;
  sources?: PDFDocument[];
};

type ThreadSummary = {
  thread_id: string;
  title: string;
  preview: string;
  updated_at: string;
  message_count: number;
};

const formatThreadTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
};

export default function Home() {
  const { toast } = useToast();
  const [messagesByThread, setMessagesByThread] = useState<
    Record<string, Message[]>
  >({});
  const [loadingByThread, setLoadingByThread] = useState<
    Record<string, boolean>
  >({});
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [input, setInput] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isResettingChat, setIsResettingChat] = useState(false);
  const [isThreadListLoading, setIsThreadListLoading] = useState(true);
  const [threadId, setThreadId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllersRef = useRef<Record<string, AbortController>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const retrievedDocsByThreadRef = useRef<Record<string, PDFDocument[]>>({});

  const messages = threadId ? messagesByThread[threadId] || [] : [];
  const isActiveThreadLoading = threadId ? !!loadingByThread[threadId] : false;

  const setThreadMessages = (
    targetThreadId: string,
    updater: Message[] | ((prev: Message[]) => Message[]),
  ) => {
    setMessagesByThread((prev) => {
      const current = prev[targetThreadId] || [];
      const nextMessages =
        typeof updater === 'function'
          ? (updater as (prev: Message[]) => Message[])(current)
          : updater;

      return {
        ...prev,
        [targetThreadId]: nextMessages,
      };
    });
  };

  const setThreadLoading = (targetThreadId: string, isLoading: boolean) => {
    setLoadingByThread((prev) => ({
      ...prev,
      [targetThreadId]: isLoading,
    }));
  };

  const clearComposerState = () => {
    setInput('');
    setFiles([]);
  };

  const abortInFlightChat = (targetThreadId?: string) => {
    if (targetThreadId) {
      abortControllersRef.current[targetThreadId]?.abort();
      delete abortControllersRef.current[targetThreadId];
      setThreadLoading(targetThreadId, false);
      delete retrievedDocsByThreadRef.current[targetThreadId];
      return;
    }

    for (const activeThreadId of Object.keys(abortControllersRef.current)) {
      abortControllersRef.current[activeThreadId]?.abort();
      setThreadLoading(activeThreadId, false);
      delete retrievedDocsByThreadRef.current[activeThreadId];
    }
    abortControllersRef.current = {};
  };

  const refreshThreadList = async (preferredThreadId?: string) => {
    setIsThreadListLoading(true);
    try {
      const response = await fetch('/api/thread', {
        method: 'GET',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const nextThreads = (data.threads || []) as ThreadSummary[];
      setThreads(nextThreads);

      if (
        preferredThreadId &&
        nextThreads.some((thread) => thread.thread_id === preferredThreadId)
      ) {
        setThreadId(preferredThreadId);
      }
    } finally {
      setIsThreadListLoading(false);
    }
  };

  const loadThread = async (nextThreadId: string) => {
    const response = await fetch(`/api/thread/${nextThreadId}`, {
      method: 'GET',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    setThreadId(data.thread_id);
    setStoredThreadId(data.thread_id);
    const hasInFlightLocalState =
      !!loadingByThread[data.thread_id] &&
      !!messagesByThread[data.thread_id]?.length;

    if (!hasInFlightLocalState) {
      setThreadMessages(
        data.thread_id,
        (data.messages || []).map(
          (message: { role: 'user' | 'assistant'; content: string }) => ({
            role: message.role,
            content: message.content,
            sources: undefined,
          }),
        ),
      );
    }
    clearComposerState();
  };

  const createFreshThread = async () => {
    const response = await fetch('/api/thread', {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    setThreadId(data.thread_id);
    setStoredThreadId(data.thread_id);
    setThreadMessages(data.thread_id, []);
    setThreadLoading(data.thread_id, false);
    await refreshThreadList(data.thread_id);
    clearComposerState();
    return data.thread_id as string;
  };

  useEffect(() => {
    let active = true;

    const init = async () => {
      try {
        const savedThreadId = getStoredThreadId();
        await refreshThreadList(savedThreadId || undefined);

        if (!active) return;

        if (savedThreadId) {
          try {
            await loadThread(savedThreadId);
            return;
          } catch {
            clearStoredThreadId();
          }
        }

        await createFreshThread();
      } catch (error) {
        console.error('Error initializing thread:', error);
        toast({
          title: 'Error',
          description:
            'Error creating thread. Please make sure you have set the backend API URL correctly. ' +
            error,
          variant: 'destructive',
        });
      }
    };

    void init();

    return () => {
      active = false;
      abortInFlightChat();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSelectThread = async (nextThreadId: string) => {
    if (
      nextThreadId === threadId ||
      isUploading ||
      isResettingChat ||
      isThreadListLoading
    ) {
      return;
    }

    try {
      await loadThread(nextThreadId);
    } catch (error) {
      console.error('Error loading thread:', error);
      toast({
        title: 'Thread load failed',
        description:
          'Could not load the selected chat.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
      await refreshThreadList();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !threadId || isResettingChat || loadingByThread[threadId]) {
      return;
    }

    const activeThreadId = threadId;
    const userMessage = input.trim();
    setThreadMessages(activeThreadId, (prev) => [
      ...prev,
      { role: 'user', content: userMessage, sources: undefined },
      { role: 'assistant', content: '', sources: undefined },
    ]);
    setInput('');
    setThreadLoading(activeThreadId, true);

    const abortController = new AbortController();
    abortControllersRef.current[activeThreadId] = abortController;
    retrievedDocsByThreadRef.current[activeThreadId] = [];

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          threadId: activeThreadId,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader available');

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkStr = decoder.decode(value);
        const lines = chunkStr.split('\n').filter(Boolean);

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const sseString = line.slice('data: '.length);
          let sseEvent: any;
          try {
            sseEvent = JSON.parse(sseString);
          } catch (err) {
            console.error('Error parsing SSE line:', err, line);
            continue;
          }

          const { event, data } = sseEvent;

          if (event === 'messages/partial' && Array.isArray(data)) {
            const lastObj = data[data.length - 1];
            if (lastObj?.type === 'ai') {
              const partialContent = lastObj.content ?? '';

              if (
                typeof partialContent === 'string' &&
                !partialContent.startsWith('{')
              ) {
                setThreadMessages(activeThreadId, (prev) => {
                  const next = [...prev];
                  if (
                    next.length > 0 &&
                    next[next.length - 1].role === 'assistant'
                  ) {
                    next[next.length - 1].content = partialContent;
                    next[next.length - 1].sources =
                      retrievedDocsByThreadRef.current[activeThreadId] || [];
                  }
                  return next;
                });
              }
            }
          } else if (event === 'updates' && data) {
            if (
              typeof data === 'object' &&
              'retrieveDocuments' in data &&
              data.retrieveDocuments &&
              Array.isArray(data.retrieveDocuments.documents)
            ) {
              retrievedDocsByThreadRef.current[activeThreadId] = (
                data as RetrieveDocumentsNodeUpdates
              ).retrieveDocuments.documents as PDFDocument[];
            } else {
              retrievedDocsByThreadRef.current[activeThreadId] = [];
            }
          }
        }
      }

      await refreshThreadList(activeThreadId);
    } catch (error) {
      if (abortController.signal.aborted) {
        return;
      }

      console.error('Error sending message:', error);
      toast({
        title: 'Error',
        description:
          'Failed to send message. Please try again.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
      setThreadMessages(activeThreadId, (prev) => {
        const next = [...prev];
        if (next.length > 0 && next[next.length - 1].role === 'assistant') {
          next[next.length - 1].content =
            'Sorry, there was an error processing your message.';
        }
        return next;
      });
    } finally {
      setThreadLoading(activeThreadId, false);
      delete abortControllersRef.current[activeThreadId];
      delete retrievedDocsByThreadRef.current[activeThreadId];
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    const nonPdfFiles = selectedFiles.filter(
      (file) => file.type !== 'application/pdf',
    );
    if (nonPdfFiles.length > 0) {
      toast({
        title: 'Invalid file type',
        description: 'Please upload PDF files only',
        variant: 'destructive',
      });
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });

      const response = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to upload files');
      }

      const data = await response.json();
      if (data.threadId) {
        setThreadId(data.threadId);
        setStoredThreadId(data.threadId);
        setThreadMessages(data.threadId, []);
        setThreadLoading(data.threadId, false);
        await refreshThreadList(data.threadId);
      }
      setFiles((prev) => [...prev, ...selectedFiles]);
      toast({
        title: 'Success',
        description: `${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''} uploaded successfully`,
        variant: 'default',
      });
    } catch (error) {
      console.error('Error uploading files:', error);
      toast({
        title: 'Upload failed',
        description:
          'Failed to upload files. Please try again.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveFile = (fileToRemove: File) => {
    setFiles((prev) => prev.filter((file) => file !== fileToRemove));
    toast({
      title: 'File removed',
      description: `${fileToRemove.name} has been removed`,
      variant: 'default',
    });
  };

  const handleNewChat = async () => {
    if (isUploading || isResettingChat) return;

    setIsResettingChat(true);

    try {
      await createFreshThread();
    } catch (error) {
      console.error('Error creating fresh chat:', error);
      toast({
        title: 'New chat failed',
        description:
          'Could not start a new chat.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
    } finally {
      setIsResettingChat(false);
    }
  };

  const handleDeleteThread = async (targetThreadId: string) => {
    if (isUploading || isResettingChat) return;

    setIsResettingChat(true);
    const deletingActiveThread = targetThreadId === threadId;

    if (deletingActiveThread) {
      abortInFlightChat(targetThreadId);
    }

    try {
      const response = await fetch(`/api/thread/${targetThreadId}`, {
        method: 'DELETE',
      });

      if (!response.ok && response.status !== 404) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (deletingActiveThread) {
        clearStoredThreadId();
        await createFreshThread();
      } else {
        abortInFlightChat(targetThreadId);
        setMessagesByThread((prev) => {
          const next = { ...prev };
          delete next[targetThreadId];
          return next;
        });
        setLoadingByThread((prev) => {
          const next = { ...prev };
          delete next[targetThreadId];
          return next;
        });
        await refreshThreadList(threadId || undefined);
      }
    } catch (error) {
      console.error('Error deleting thread:', error);
      toast({
        title: 'Delete chat failed',
        description:
          'Could not delete the chat.\n' +
          (error instanceof Error ? error.message : 'Unknown error'),
        variant: 'destructive',
      });
    } finally {
      setIsResettingChat(false);
    }
  };

  return (
    <main className="flex min-h-screen bg-background">
      <aside className="hidden md:flex md:w-80 md:flex-col md:border-r md:bg-muted/30">
        <div className="border-b p-4">
          <Button
            type="button"
            className="w-full justify-start"
            onClick={handleNewChat}
            disabled={isUploading || isResettingChat}
          >
            {isResettingChat ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            New chat
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          <div className="mb-3 px-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Threads
          </div>

          <div className="space-y-2">
            {isThreadListLoading ? (
              <div className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading chats...
              </div>
            ) : threads.length === 0 ? (
              <div className="rounded-xl border border-dashed bg-background/80 p-4 text-sm text-muted-foreground">
                No chats yet.
              </div>
            ) : (
              threads.map((thread) => {
                const isActive = thread.thread_id === threadId;

                return (
                  <div
                    key={thread.thread_id}
                    className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                      isActive
                        ? 'border-foreground bg-background shadow-sm'
                        : 'border-transparent bg-background/70 hover:border-border hover:bg-background'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 rounded-lg bg-muted p-2">
                        <MessageSquare className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => void handleSelectThread(thread.thread_id)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <p className="truncate text-sm font-medium">
                                {thread.title}
                              </p>
                              <span className="shrink-0 text-[11px] text-muted-foreground">
                                {formatThreadTime(thread.updated_at)}
                              </span>
                            </div>
                            <p className="mt-1 max-h-10 overflow-hidden text-xs text-muted-foreground">
                              {thread.preview}
                            </p>
                          </button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-destructive"
                            disabled={isResettingChat || isUploading}
                            onClick={() => void handleDeleteThread(thread.thread_id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <div className="mt-3 flex items-center justify-between">
                          <span className="text-[11px] text-muted-foreground">
                            {thread.message_count} msg
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </aside>

      <section className="flex min-h-screen flex-1 flex-col">
        <div className="border-b px-4 py-3 md:hidden">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleNewChat}
            disabled={isUploading || isResettingChat}
          >
            {isResettingChat ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            New chat
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          {messages.length === 0 ? (
            <div className="mx-auto flex max-w-4xl flex-col">
              <div className="flex min-h-[50vh] items-center justify-center">
                <div className="text-center">
                  <p className="mx-auto max-w-md font-medium text-muted-foreground">
                    This ai chatbot is an example template to accompany the
                    book:{' '}
                    <a
                      href="https://www.oreilly.com/library/view/learning-langchain/9781098167271/"
                      className="underline hover:text-foreground"
                    >
                      Learning LangChain (O&apos;Reilly): Building AI and LLM
                      applications with LangChain and LangGraph
                    </a>
                  </p>
                </div>
              </div>
              <ExamplePrompts onPromptSelect={setInput} />
            </div>
          ) : (
            <div className="mx-auto mb-28 w-full max-w-4xl space-y-4">
              {messages.map((message, index) => (
                <ChatMessage key={index} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="sticky bottom-0 border-t bg-background/95 p-4 backdrop-blur">
          <div className="mx-auto max-w-4xl space-y-4">
            {files.length > 0 && (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {files.map((file, index) => (
                  <FilePreview
                    key={`${file.name}-${index}`}
                    file={file}
                    onRemove={() => handleRemoveFile(file)}
                  />
                ))}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="flex gap-2 rounded-2xl border bg-gray-50">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".pdf"
                  multiple
                  className="hidden"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-12 rounded-none rounded-l-2xl"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading || isActiveThreadLoading || isResettingChat}
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Paperclip className="h-4 w-4" />
                  )}
                </Button>
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={
                    isUploading ? 'Uploading PDF...' : 'Send a message...'
                  }
                  className="h-12 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
                  disabled={
                    isUploading ||
                    isActiveThreadLoading ||
                    isResettingChat ||
                    !threadId
                  }
                />
                <Button
                  type="submit"
                  size="icon"
                  className="h-12 rounded-none rounded-r-2xl"
                  disabled={
                    !input.trim() ||
                    isUploading ||
                    isActiveThreadLoading ||
                    isResettingChat ||
                    !threadId
                  }
                >
                  {isActiveThreadLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowUp className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </main>
  );
}
