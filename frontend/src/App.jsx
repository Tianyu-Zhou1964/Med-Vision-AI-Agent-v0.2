// frontend/src/App.jsx

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { 
  Upload, Image as ImageIcon, Send, FileText, 
  Trash2, Video, Activity, X, ChevronLeft, ChevronRight, 
  Download, Maximize2, Box, Square, Eraser, Sparkles, CheckCircle2, 
  Play, FileVideo, Monitor
} from 'lucide-react';
import './App.css'; 

const API_BASE = ""; 

const GeminiLoader = ({ size = "normal", showText = true, text = "Thinking..." }) => (
  <div className="gemini-loader-container">
    <div className={`gemini-star ${size}`}></div>
    {showText && <span className="gemini-text">{text}</span>}
  </div>
);

function App() {
  const [modelStatus, setModelStatus] = useState("Ready");
  const [currentModelName, setCurrentModelName] = useState("yolo11n.pt (Default)");
  const [activeTab, setActiveTab] = useState('image'); 
  
  const [previewFiles, setPreviewFiles] = useState([]); 
  const [inferenceResults, setInferenceResults] = useState([]); 
  const [imageFiles, setImageFiles] = useState([]); 
  const [videoFile, setVideoFile] = useState(null);
  const [videoPreview, setVideoPreview] = useState(null);
  const [videoResult, setVideoResult] = useState(null);
  
  const [resultText, setResultText] = useState("");
  const [stats, setStats] = useState({ conf: 0, fps: 0 });
  const [contextPath, setContextPath] = useState(null); 
  const [isLoading, setIsLoading] = useState(false);
  const [videoProgress, setVideoProgress] = useState(0); 
  const [progressLog, setProgressLog] = useState("");
  
  const [chatHistory, setChatHistory] = useState([]); 
  const [inputMsg, setInputMsg] = useState("");
  const [isChatting, setIsChatting] = useState(false);
  
  const abortControllerRef = useRef(null);
  const chatEndRef = useRef(null);
  const modelInputRef = useRef(null);
  const imageInputRef = useRef(null);
  const videoInputRef = useRef(null);

  const [lightboxIndex, setLightboxIndex] = useState(-1);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const isUploading = modelStatus.toLowerCase().includes("uploading");
  const isGlobalBusy = isLoading || isChatting || isUploading;

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatHistory, isChatting]);
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!lightboxOpen) return;
      if (e.key === 'ArrowLeft') prevImage(e);
      if (e.key === 'ArrowRight') nextImage(e);
      if (e.key === 'Escape') closeLightbox();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [lightboxOpen, lightboxIndex]);

  const uploadModelFile = async (file) => {
    if (!file || !file.name.endsWith('.pt')) return alert("Please upload a .pt file!");
    setModelStatus(`Uploading ${file.name}...`);
    const formData = new FormData(); formData.append('file', file);
    try {
      await axios.post(`${API_BASE}/api/upload_model`, formData);
      setModelStatus("Model Loaded");
      setCurrentModelName(file.name);
    } catch (err) { setModelStatus("Upload Failed"); }
  };
  const handleModelInput = (e) => uploadModelFile(e.target.files[0]);
  const onDropModel = (e) => { e.preventDefault(); e.stopPropagation(); if(e.dataTransfer.files[0]) uploadModelFile(e.dataTransfer.files[0]); };
  const onDragOver = (e) => e.preventDefault();
  const clearModel = () => { setCurrentModelName(null); setModelStatus("Ready"); };

  const handleImageFiles = (files) => {
    if (!files || !files.length) return;
    const fileArray = Array.from(files);
    setImageFiles(fileArray); 
    setPreviewFiles(fileArray.map(f => URL.createObjectURL(f)));
    setInferenceResults(new Array(fileArray.length).fill(null));
    setResultText("Images loaded.");
  };
  const onDropImage = (e) => { e.preventDefault(); if (e.dataTransfer.files.length) handleImageFiles(e.dataTransfer.files); };
  
  const handleRunImageInference = async () => {
    if (!imageFiles.length) return alert("Select images!");
    setIsLoading(true); setResultText("Thinking...");
    const formData = new FormData(); imageFiles.forEach(f => formData.append('files', f));
    try {
      const res = await axios.post(`${API_BASE}/api/detect_image`, formData);
      setInferenceResults(res.data.images); setResultText(res.data.text);
      setStats({ conf: res.data.conf || 0, fps: 0 }); setContextPath(res.data.context_path);
      if (!currentModelName) setCurrentModelName("yolo11n.pt (Default)");
    } catch (err) { setResultText("Error: " + err.message); } finally { setIsLoading(false); }
  };

  const handleVideoFile = (file) => { if(file) { setVideoFile(file); setVideoPreview(URL.createObjectURL(file)); setVideoResult(null); setVideoProgress(0); setProgressLog(""); }};
  const onDropVideo = (e) => { e.preventDefault(); if(e.dataTransfer.files[0]) handleVideoFile(e.dataTransfer.files[0]); };
  
  const handleRunVideoInference = async () => {
    if (!videoFile) return alert("Upload video!");
    setIsLoading(true); setResultText("Initializing video stream...");
    setVideoProgress(0); setProgressLog("Starting...");
    const formData = new FormData(); formData.append('file', videoFile);
    try {
      const response = await fetch(`${API_BASE}/api/detect_video`, { method: 'POST', body: formData });
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); 
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const msg = JSON.parse(line);
                if (msg.type === 'progress') { setVideoProgress(msg.percent); setProgressLog(msg.log); } 
                else if (msg.type === 'result') {
                    setVideoResult(msg.data.video_url); setResultText(msg.data.text);
                    setStats({ conf: 0, fps: msg.data.fps }); setContextPath(msg.data.context_path);
                    setVideoProgress(100); setProgressLog("Complete!");
                } else if (msg.type === 'error') { setResultText("Error: " + msg.message); }
            } catch (e) { console.error(e); }
        }
      }
      if (!currentModelName) setCurrentModelName("yolo11n.pt (Default)");
    } catch (err) { setResultText("Error: " + err.message); } finally { setIsLoading(false); }
  };

  const handleStopChat = () => {
      if (abortControllerRef.current) {
          abortControllerRef.current.abort(); abortControllerRef.current = null; setIsChatting(false);
          setChatHistory(p => { const n=[...p]; if(n.length) n[n.length-1][1]+=" *(Stopped)*"; return n; });
      }
  };
  const handleClearChat = () => { if(!isChatting && window.confirm("Clear chat?")) setChatHistory([]); };
  const handleSendChat = async () => {
    if (!inputMsg.trim()) return;
    const msg = inputMsg; setInputMsg(""); setIsChatting(true);
    setChatHistory(prev => [...prev, [msg, ""]]);
    abortControllerRef.current = new AbortController();
    try {
      const res = await fetch(`${API_BASE}/api/chat_stream`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ message: msg, history: chatHistory, context_path: contextPath }),
        signal: abortControllerRef.current.signal
      });
      const reader = res.body.getReader(); const decoder = new TextDecoder(); let botText = "";
      while(true) {
        const {done, value} = await reader.read(); if(done) break;
        botText += decoder.decode(value, {stream:true});
        setChatHistory(p => { const n=[...p]; if(n.length) n[n.length-1][1]=botText; return n; });
      }
    } catch(err) { if(err.name!=='AbortError') console.error(err); } 
    finally { setIsChatting(false); abortControllerRef.current = null; }
  };
  const generateReport = async () => {
    if(!chatHistory.length) return alert("Empty chat.");
    try {
        const res = await axios.post(`${API_BASE}/api/generate_report`, {message:"", history:chatHistory, context_path:contextPath});
        window.open(res.data.report_url, '_blank');
    } catch(e) { alert("Failed."); }
  };

  const openLightbox = (i) => { setLightboxIndex(i); setLightboxOpen(true); };
  const closeLightbox = () => setLightboxOpen(false);
  const nextImage = (e) => { e?.stopPropagation(); setLightboxIndex(p => (p + 1) % previewFiles.length); };
  const prevImage = (e) => { e?.stopPropagation(); setLightboxIndex(p => (p - 1 + previewFiles.length) % previewFiles.length); };
  const downloadFile = (url, name) => {
      const link = document.createElement('a'); link.href = url; link.download = name;
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
  };

  return (
    <div className="app-layout">
      <header className="navbar">
        <div className="brand"><Activity size={24} className="text-blue-400"/><h1>Med Vision AI</h1></div>
        <div className="status-pill">
            {isGlobalBusy ? <><GeminiLoader size="small" showText={false} /><span>Processing...</span></> : <><CheckCircle2 size={14} /><span>{modelStatus}</span></>}
        </div>
      </header>

      <div className="content-grid">
        <aside className="sidebar">
          <div className="panel">
            <h3>Active Model</h3>
            {currentModelName ? (
                <div className="active-model-card">
                    <div className="model-icon"><Box size={24}/></div>
                    <div className="model-info">
                        <span className="label">System Ready</span>
                        <span className="name">{currentModelName}</span>
                    </div>
                    <button className="clear-model-btn" onClick={clearModel} title="Remove Model"><X size={14}/></button>
                </div>
            ) : (
                <div className="file-drop-area" onClick={()=>modelInputRef.current.click()} onDrop={onDropModel} onDragOver={onDragOver}>
                    <Upload size={24} strokeWidth={1.5}/><span>Upload Custom .pt</span>
                    <input type="file" ref={modelInputRef} hidden accept=".pt" onChange={handleModelInput}/>
                </div>
            )}
          </div>
          <div className="panel flex-grow">
            <h3>System Logs</h3>
            <div className="stats-row">
                <div className="stat"><span>Confidence</span><strong>{stats.conf?.toFixed(2)}</strong></div>
                <div className="stat"><span>FPS</span><strong>{stats.fps?.toFixed(2)}</strong></div>
            </div>
            {isLoading && activeTab === 'video' && (
                <div className="progress-container">
                    <div className="progress-label"><span>{progressLog}</span><span>{videoProgress}%</span></div>
                    <div className="progress-bar-bg"><div className="progress-bar-fill" style={{width: `${videoProgress}%`}}></div></div>
                </div>
            )}
            <textarea className="log-console" readOnly value={resultText}></textarea>
          </div>
        </aside>

        <main className="workspace">
          <div className="tabs">
            <button className={`tab-btn ${activeTab==='image'?'active':''}`} onClick={()=>setActiveTab('image')}><ImageIcon size={16}/> Image Analysis</button>
            <button className={`tab-btn ${activeTab==='video'?'active':''}`} onClick={()=>setActiveTab('video')}><Video size={16}/> Video Analysis</button>
          </div>
          <div className="workspace-content">
            {activeTab === 'image' ? (
              <div className="image-mode">
                <div className="drop-zone" onDrop={onDropImage} onDragOver={onDragOver} onClick={()=>imageInputRef.current.click()}>
                   <input type="file" ref={imageInputRef} multiple hidden accept="image/*" onChange={(e)=>handleImageFiles(e.target.files)}/>
                   <Upload size={32} strokeWidth={1.5}/><p style={{marginTop:10}}>Click or Drag Images</p>
                </div>
                <button className="run-btn" onClick={handleRunImageInference} disabled={isLoading || !imageFiles.length}>
                    {isLoading ? <><GeminiLoader size="small" showText={false} /> Analyzing...</> : 'Analyze Image'}
                </button>
                <div className="gallery-container">
                    {!previewFiles.length && <div className="placeholder" style={{color:'#666', marginTop:20}}>Awaiting input...</div>}
                    <div className="img-grid">
                        {previewFiles.map((src, i) => (
                            <div key={i} className="img-card" onClick={()=>openLightbox(i)}>
                                <img src={inferenceResults[i] || src} alt={`img-${i}`} />
                                <div className="img-overlay"><Maximize2 size={20}/></div>
                                {inferenceResults[i] && <div className="status-badge">Detected</div>}
                            </div>
                        ))}
                    </div>
                </div>
                <button className="clear-btn" onClick={()=>{setPreviewFiles([]); setInferenceResults([]); setImageFiles([])}}><Trash2 size={14}/> Clear All</button>
              </div>
            ) : (
              <div className="video-mode">
                 <div className="drop-zone" style={{height:100}} onDrop={onDropVideo} onDragOver={onDragOver} onClick={()=>videoInputRef.current.click()}>
                     <input type="file" ref={videoInputRef} hidden accept="video/*" onChange={(e)=>handleVideoFile(e.target.files[0])}/>
                     <Upload size={32}/><p>{videoFile ? videoFile.name : "Upload Video"}</p>
                 </div>
                 
                 <button className="run-btn" onClick={handleRunVideoInference} disabled={isLoading || !videoFile}>
                     {isLoading ? <><GeminiLoader size="small" showText={false} /> Processing...</> : 'Analyze Video (Step 5)'}
                 </button>
                 
                 <div className="video-compare">
                    {/* 🔥 核心修复：添加 key 属性以强制重载，并使用 contain 样式 */}
                    <div className="v-box">
                        <div className="video-label"><FileVideo size={14}/> Input</div>
                        {videoPreview && <video controls src={videoPreview}/>}
                    </div>
                    <div className="v-box">
                        <div className="video-label"><Monitor size={14}/> Result</div>
                        {videoResult ? (
                            <video key={videoResult} controls src={videoResult} />
                        ) : null}
                    </div>
                 </div>
              </div>
            )}
          </div>
        </main>

        <aside className="chat-panel">
           {/* Chat Panel Content */}
           <div className="chat-head">
              <div style={{display:'flex', alignItems:'center', gap:8}}><Sparkles size={18} className="text-purple-400"/><h3>AI Assistant</h3></div>
              <div className="chat-actions"><button className="icon-btn" onClick={handleClearChat} disabled={isChatting} title="Clear Chat"><Eraser size={16}/></button><button className="icon-btn" onClick={generateReport} title="Export PDF"><FileText size={16}/></button></div>
           </div>
           <div className="chat-list">
              {!chatHistory.length && <div className="empty-chat" style={{opacity:0.3, textAlign:'center', marginTop:50}}><Activity size={40}/><p>Waiting for context...</p></div>}
              {chatHistory.map((pair, i) => (
                  <React.Fragment key={i}>
                      <div className="msg user"><div className="bubble">{pair[0]}</div></div>
                      <div className="msg bot"><div className="bubble">{pair[1] === "" ? <GeminiLoader /> : <ReactMarkdown>{pair[1]}</ReactMarkdown>}</div></div>
                  </React.Fragment>
              ))}
              <div ref={chatEndRef}></div>
           </div>
           <div className="chat-input-area">
              <textarea placeholder="Ask something..." value={inputMsg} onChange={e=>setInputMsg(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();handleSendChat()}}}/>
              {isChatting ? <button className="stop-btn" onClick={handleStopChat}><Square size={16} fill="white" /></button> : <button onClick={handleSendChat}><Send size={18}/></button>}
           </div>
        </aside>
      </div>

      {lightboxOpen && lightboxIndex >= 0 && (
          <div className="lightbox-overlay" onClick={closeLightbox}>
             {/* Lightbox content */}
              <div className="lightbox-container" onClick={e=>e.stopPropagation()}>
                  <div className="lb-header"><span>Image {lightboxIndex+1} / {previewFiles.length}</span><button className="lb-close-btn" onClick={closeLightbox}><X size={24}/></button></div>
                  <div className="lb-content">
                      <div className="lb-pane"><div className="lb-pane-head">Input <button onClick={()=>downloadFile(previewFiles[lightboxIndex], `orig.jpg`)}><Download size={14}/></button></div><img src={previewFiles[lightboxIndex]} alt="orig" /></div>
                      <div className="lb-pane"><div className="lb-pane-head">Output <button onClick={()=>downloadFile(inferenceResults[lightboxIndex], `res.jpg`)} disabled={!inferenceResults[lightboxIndex]}><Download size={14}/></button></div>{inferenceResults[lightboxIndex] ? <img src={inferenceResults[lightboxIndex]} alt="res" /> : <div className="lb-empty">Processing...</div>}</div>
                  </div>
                  <button className="lb-nav prev" onClick={prevImage}><ChevronLeft size={30}/></button>
                  <button className="lb-nav next" onClick={nextImage}><ChevronRight size={30}/></button>
              </div>
          </div>
      )}
    </div>
  );
}

export default App;