import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '1m',
}

const apiBaseUrl = __ENV.API_BASE_URL || 'http://localhost:8000'
const pdfPath = __ENV.PDF_PATH || 'sample.pdf'
const pdfBytes = open(pdfPath, 'b')

export default function () {
  const createResponse = http.post(
    `${apiBaseUrl}/chat/jobs`,
    {
      query: 'What are the key findings?',
      files: http.file(pdfBytes, 'sample.pdf', 'application/pdf'),
    },
  )

  check(createResponse, {
    'job accepted': (response) => response.status === 202,
  })

  if (createResponse.status !== 202) {
    return
  }

  const job = createResponse.json()
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const pollResponse = http.get(`${apiBaseUrl}/chat/jobs/${job.job_id}`)
    check(pollResponse, {
      'poll ok': (response) => response.status === 200,
    })

    const payload = pollResponse.json()
    if (payload.status === 'completed' || payload.status === 'failed') {
      break
    }
    sleep(1)
  }
}
