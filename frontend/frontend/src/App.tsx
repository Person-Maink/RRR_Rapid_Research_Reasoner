import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import './App.css'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ??
  'http://localhost:8000'

type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'

type RetrievedPage = {
  document_id: string
  file_name: string
  page_number: number
  pdf_url: string
  score?: number | null
}

type ChatJobCreated = {
  job_id: string
  status: JobStatus
  poll_url: string
}

type ChatJobResponse = {
  job_id: string
  status: JobStatus
  answer?: string | null
  retrieved_pages: RetrievedPage[]
  error?: string | null
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  status?: JobStatus
  files?: string[]
  citations?: RetrievedPage[]
}

function App() {
  const [query, setQuery] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Upload PDFs, ask a research question, and I will retrieve the most relevant cited pages.',
    },
  ])
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError('')

    const cleanQuery = query.trim()
    if (!cleanQuery) {
      setFormError('Add a question before sending.')
      return
    }
    if (files.length === 0) {
      setFormError('Upload at least one PDF.')
      return
    }

    setIsSubmitting(true)
    const assistantId = crypto.randomUUID()
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text: cleanQuery,
      files: files.map((file) => file.name),
    }
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      text: 'Queued for ingestion. I will update this reply as the worker processes your PDFs.',
      status: 'queued',
    }

    setMessages((current) => [...current, userMessage, assistantMessage])

    try {
      const formData = new FormData()
      formData.append('query', cleanQuery)
      files.forEach((file) => formData.append('files', file))

      const response = await fetch(`${API_BASE_URL}/chat/jobs`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const created = (await response.json()) as ChatJobCreated
      setQuery('')
      setFiles([])
      await pollJob(created.job_id, assistantId)
    } catch (error) {
      updateAssistantMessage(assistantId, {
        text:
          error instanceof Error
            ? error.message
            : 'Something went wrong while creating the job.',
        status: 'failed',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  async function pollJob(jobId: string, assistantId: string) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const response = await fetch(`${API_BASE_URL}/chat/jobs/${jobId}`)
      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const job = (await response.json()) as ChatJobResponse
      if (job.status === 'completed') {
        updateAssistantMessage(assistantId, {
          text: job.answer ?? 'Retrieval completed.',
          status: 'completed',
          citations: job.retrieved_pages,
        })
        return
      }

      if (job.status === 'failed') {
        updateAssistantMessage(assistantId, {
          text: job.error ?? 'The worker could not process this request.',
          status: 'failed',
        })
        return
      }

      updateAssistantMessage(assistantId, {
        text:
          job.status === 'processing'
            ? 'Processing PDFs and building retrieval context...'
            : 'Waiting for a worker to pick up the job...',
        status: job.status,
      })
      await delay(1500)
    }

    updateAssistantMessage(assistantId, {
      text: 'This job is still running. Try refreshing the status in a moment.',
      status: 'processing',
    })
  }

  function updateAssistantMessage(
    id: string,
    patch: Partial<Pick<ChatMessage, 'text' | 'status' | 'citations'>>,
  ) {
    setMessages((current) =>
      current.map((message) =>
        message.id === id ? { ...message, ...patch } : message,
      ),
    )
  }

  return (
    <main className="app-shell">
      <section className="chat-panel" aria-label="PDF research chat">
        <header className="hero">
          <p className="eyebrow">Rapid Research Reasoner</p>
          <h1>Ask your PDFs. Inspect the evidence.</h1>
          <p>
            Upload papers, send a question, and the async retrieval pipeline
            returns cited pages directly in the chat.
          </p>
        </header>

        <section className="messages" aria-live="polite">
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))}
        </section>

        <form className="composer" onSubmit={handleSubmit}>
          <label className="upload-drop">
            <input
              type="file"
              accept="application/pdf,.pdf"
              multiple
              onChange={(event) => {
                const selected = Array.from(event.target.files ?? [])
                const pdfs = selected.filter((file) =>
                  file.name.toLowerCase().endsWith('.pdf'),
                )
                setFiles(pdfs)
                setFormError(
                  selected.length !== pdfs.length
                    ? 'Only PDF files were kept.'
                    : '',
                )
              }}
            />
            <span>Upload PDFs</span>
            <strong>
              {files.length > 0
                ? files.map((file) => file.name).join(', ')
                : 'Drop in the source papers'}
            </strong>
          </label>

          <div className="query-row">
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What should I retrieve from these PDFs?"
              rows={3}
            />
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Working...' : 'Send'}
            </button>
          </div>
          {formError ? <p className="form-error">{formError}</p> : null}
        </form>
      </section>
    </main>
  )
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const activeCitation = message.citations?.[activeIndex]

  return (
    <article className={`message ${message.role}`}>
      <div className="message-meta">
        <span>{message.role === 'user' ? 'You' : 'Reasoner'}</span>
        {message.status ? <StatusPill status={message.status} /> : null}
      </div>
      <p>{message.text}</p>
      {message.files ? (
        <ul className="file-list">
          {message.files.map((file) => (
            <li key={file}>{file}</li>
          ))}
        </ul>
      ) : null}

      {message.citations && message.citations.length > 0 ? (
        <section className="citation-viewer">
          <div className="citation-tabs">
            {message.citations.map((citation, index) => (
              <button
                key={`${citation.document_id}-${citation.page_number}`}
                className={index === activeIndex ? 'active' : ''}
                type="button"
                onClick={() => setActiveIndex(index)}
              >
                {citation.file_name} p.{citation.page_number}
              </button>
            ))}
          </div>
          {activeCitation ? <PdfViewer citation={activeCitation} /> : null}
        </section>
      ) : null}
    </article>
  )
}

function StatusPill({ status }: { status: JobStatus }) {
  return <span className={`status ${status}`}>{status}</span>
}

function PdfViewer({ citation }: { citation: RetrievedPage }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [viewerState, setViewerState] = useState('Loading cited page...')

  useEffect(() => {
    let cancelled = false

    async function renderPage() {
      const canvas = canvasRef.current
      if (!canvas) {
        return
      }

      setViewerState('Loading cited page...')
      try {
        const loadingTask = pdfjsLib.getDocument(citation.pdf_url)
        const pdf = await loadingTask.promise
        const page = await pdf.getPage(citation.page_number)
        const viewport = page.getViewport({ scale: 1.25 })
        const context = canvas.getContext('2d')

        if (!context || cancelled) {
          return
        }

        canvas.width = viewport.width
        canvas.height = viewport.height
        await page.render({ canvasContext: context, viewport }).promise

        if (!cancelled) {
          setViewerState(
            `${citation.file_name}, page ${citation.page_number}`,
          )
        }
      } catch {
        if (!cancelled) {
          setViewerState('Could not render this PDF page.')
        }
      }
    }

    renderPage()
    return () => {
      cancelled = true
    }
  }, [citation])

  return (
    <div className="pdf-frame">
      <div className="pdf-toolbar">
        <span>{viewerState}</span>
        <a href={citation.pdf_url} target="_blank" rel="noreferrer">
          Open PDF
        </a>
      </div>
      <canvas ref={canvasRef} aria-label={viewerState} />
    </div>
  )
}

async function readError(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `Request failed with ${response.status}`
  } catch {
    return `Request failed with ${response.status}`
  }
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export default App
