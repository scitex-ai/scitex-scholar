/** Render an authorized saved PDF with Live Paper's public viewer component. */
export async function mountLibraryPdf(container, assets, document, signal) {
  const [{ createRichPdfViewer }, { createPdfViewer }, pdfjs] = await Promise.all([
    import(assets.pdfProvider),
    import(assets.pdfFactory),
    import(assets.pdfjs),
  ]);
  signal.throwIfAborted();
  const viewer = createRichPdfViewer({
    container,
    createPdfViewer,
    rendererOptions: {
      pdfjs,
      workerSrc: assets.pdfWorker,
      textLayer: true,
      linkLayer: true,
    },
    ports: { documents: { resolve: () => ({ ...document, readonly: true }) } },
  });
  viewer.renderer.setInteractive(false);
  signal.addEventListener("abort", () => viewer.destroy(), { once: true });
  try {
    await viewer.load(document.id);
    signal.throwIfAborted();
    await viewer.renderer.fitWidth();
  } catch (error) {
    viewer.destroy();
    throw error;
  }
}
