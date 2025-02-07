import { useState } from "react";
import "./FileUpload.css"; // Import custom CSS for styling
import API_BASE_URL from "../App";
function FileUpload() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [outputFile, setOutputFile] = useState("");
  const [loading, setLoading] = useState(false);
  const [scraping, setScraping] = useState(false);
  // const API_BASE_URL = "http://127.0.0.1:5000";
  // const API_BASE_URL = "http://192.168.0.28:5000";
  // const API_BASE_URL = "https://127.0.0.1:5000.railway.app";

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    console.log("Selected File:", selectedFile); // Debugging log

    if (selectedFile) {
      const validExtensions = ["xlsx", "xls"];
      const fileExtension = selectedFile.name.split(".").pop().toLowerCase();

      if (!validExtensions.includes(fileExtension)) {
        setMessage(
          "Invalid file format. Please upload an Excel file (.xlsx or .xls)."
        );
        setFile(null);
      } else {
        setFile(selectedFile);
        setMessage(""); // Clear previous messages
      }
    }
  };

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!file) {
      setMessage("Please select a valid Excel file to upload.");
      return;
    }

    setLoading(true);
    setMessage("Uploading file...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("File upload failed.");
      }

      const result = await response.json();
      scrapeUrls(result.filepath);
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const scrapeUrls = async (filepath) => {
    setScraping(true);

    try {
      const response = await fetch(`${API_BASE_URL}/scrape`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filepath }),
      });

      if (!response.ok) {
        throw new Error("Scraping failed.");
      }

      const result = await response.json();
      setMessage("Scraping completed successfully");
      setOutputFile(result.output_file);
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setScraping(false);
      setLoading(false);
    }
  };

  return (
    <div className="file-upload-container fade-in">
      <h2>Upload an Excel File for Web Scraping</h2>
      <form onSubmit={handleUpload} className="upload-form">
        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileChange}
          className="file-input"
        />
        {file && <p>Selected File: {file.name}</p>} {/* Show selected file */}
        <button
          type="submit"
          disabled={loading || scraping}
          className={`upload-button ${loading ? "loading" : ""}`}
        >
          {loading || scraping ? "Processing..." : "Upload & Scrape"}
        </button>
      </form>
      {loading && (
        <div>
          <div className="spinner"></div>
          <p className="loading-text">Processing...</p>
        </div>
      )}
      {scraping && (
        <div>
          <div className="spinner"></div>
          <p className="scraping-text">Scraping URLs...</p>
        </div>
      )}
      {message && <p className="message-text">{message}</p>}
      {outputFile && !loading && !scraping && (
        <a href={`${API_BASE_URL}/download/${outputFile}`} download>
          <button className="download-button">Download file</button>
        </a>
      )}
    </div>
  );
}

export default FileUpload;
