<script>
  import JSZip from 'jszip'

  const maxStar = Number(import.meta.env.VITE_MAX_STAR || 16)
  const configuredBase = import.meta.env.VITE_PLAYLIST_BASE_URL || '/playlists'
  const baseUrl = configuredBase.replace(/\/$/, '')

  let state = 'idle'
  let message = ''
  let foundCount = 0

  async function downloadPlaylists() {
    if (state === 'loading') return

    state = 'loading'
    message = 'Collecting ranked playlists...'
    foundCount = 0

    const zip = new JSZip()
    const requests = Array.from({ length: maxStar + 1 }, async (_, star) => {
      const filename = `ranked_star_${String(star).padStart(2, '0')}.bplist`

      try {
        const response = await fetch(`${baseUrl}/${filename}`)
        if (!response.ok) return
        zip.file(filename, await response.blob())
        foundCount += 1
      } catch {
        // Missing star buckets are expected when no maps exist for that range.
      }
    })

    await Promise.all(requests)

    if (!foundCount) {
      state = 'error'
      message = 'No playlists found. Please try again later.'
      return
    }

    message = `Compressing ${foundCount} playlist${foundCount === 1 ? '' : 's'}...`
    const archive = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } })
    const url = URL.createObjectURL(archive)
    const link = document.createElement('a')
    link.href = url
    link.download = 'scoresaber-ranked-playlists.zip'
    link.click()
    URL.revokeObjectURL(url)

    state = 'success'
    message = `${foundCount} playlist${foundCount === 1 ? '' : 's'} ready to play.`
  }
</script>

<svelte:head>
  <meta property="og:title" content="ScoreSaber Ranked Playlists" />
  <meta property="og:description" content="Download every ranked playlist as one ZIP." />
</svelte:head>

<main class="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-12">
  <div class="ambient ambient-one" aria-hidden="true"></div>
  <div class="ambient ambient-two" aria-hidden="true"></div>

  <section class="relative z-10 flex w-full max-w-2xl flex-col items-center text-center">

    <button
      class="download-button group mt-11 flex min-h-16 w-full max-w-md items-center justify-center gap-3 px-7 text-base font-bold text-white sm:text-lg"
      class:loading={state === 'loading'}
      onclick={downloadPlaylists}
      disabled={state === 'loading'}
      aria-label="Download all ScoreSaber ranked playlists"
    >
      {#if state === 'loading'}
        <span class="spinner" aria-hidden="true"></span>
        <span>{message}</span>
      {:else}
        <span>{state === 'success' ? 'Download again' : 'Download ScoreSaber Ranked Playlists'}</span>
      {/if}
    </button>
  </section>
</main>
