export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-center">
      <div>
        <div className="text-6xl mb-4" aria-hidden="true">&#128269;</div>
        <h1 className="text-2xl font-bold text-white mb-2">Page not found</h1>
        <a href="/" className="text-purple-400 text-sm hover:underline focus:outline-none focus:ring-2 focus:ring-purple-500 rounded">
          &larr; Back to marketplace
        </a>
      </div>
    </div>
  );
}
