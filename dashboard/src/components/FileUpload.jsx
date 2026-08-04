export default function FileUpload({ selectedFile, onFileSelect }) {
  return (
    <div className="file-upload">
      <label className="file-upload__label" htmlFor="log-file">
        <span className="file-upload__title">Upload log file</span>
        <span className="file-upload__hint">Select a .log file from your machine</span>
      </label>
      <input
        id="log-file"
        type="file"
        accept=".log,.txt"
        className="file-upload__input"
        onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
      />
      {selectedFile && (
        <p className="file-upload__name">
          Selected: <strong>{selectedFile.name}</strong> ({Math.round(selectedFile.size / 1024)} KB)
        </p>
      )}
    </div>
  )
}
