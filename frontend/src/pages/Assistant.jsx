import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { API_BASE_URL } from '../config/api';
import { 
  Send, 
  Mic, 
  Bot, 
  User, 
  Volume2, 
  VolumeX, 
  Play, 
  Pause, 
  Paperclip, 
  Trash2, 
  AlertCircle, 
  Sparkles, 
  Loader2, 
  Camera, 
  RefreshCw, 
  X, 
  CheckCircle, 
  AlertTriangle,
  Image as ImageIcon
} from 'lucide-react';

export default function Assistant() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const apiUrl = API_BASE_URL;
  const initialContext = location.state?.initialCropContext;


  const [messages, setMessages] = useState(() => {
    const defaultMsg = { 
      id: 1, 
      type: 'ai', 
      text: i18n.language === 'en' 
        ? "Hello! I'm AgroNex AI. You can speak to me using the mic, take a live photo of your crop leaf with the camera, or type your farming questions below." 
        : "வணக்கம்! நான் அக்ரோநெக்ஸ் AI. நீங்கள் மைக்ரோஃபோன் மூலம் பேசலாம், கேமரா மூலம் பயிர் இலையை படம் பிடிக்கலாம் அல்லது கீழே தட்டச்சு செய்யலாம்." 
    };
    if (initialContext) {
      const condName = (initialContext.condition || '').replace(/_/g, ' ');
      return [
        defaultMsg,
        {
          id: 2,
          type: 'ai',
          text: i18n.language === 'ta'
            ? `நான் உங்கள் ${initialContext.crop} பயிரின் முடிவுகளைப் பெற்றுள்ளேன் (${condName}). தெளிப்பு ஆலோசனை அல்லது சிகிச்சை பற்றி என்னிடம் கேளுங்கள்.`
            : `I have received the diagnostic context for your ${initialContext.crop} (${condName}). Ask me about weather-grounded spray windows or treatment steps.`,
          cropAnalysis: initialContext,
        }
      ];
    }
    return [defaultMsg];
  });
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordedAudio, setRecordedAudio] = useState(null); // { file, url, name, duration }
  const [waveBars, setWaveBars] = useState(() => Array(32).fill(6));

  // Photo / Camera State
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [cameraFacing, setCameraFacing] = useState('environment'); // 'environment' | 'user'
  const [capturedPhoto, setCapturedPhoto] = useState(null); // { file, url, name }
  const [cameraActive, setCameraActive] = useState(false);

  // Audio Playback State
  const [activeAudioId, setActiveAudioId] = useState(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [previewPlaying, setPreviewPlaying] = useState(false);

  // References
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const pcmBuffersRef = useRef([]);
  const scriptProcessorRef = useRef(null);
  const isRecordingRef = useRef(false);
  const timerIntervalRef = useRef(null);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const animFrameRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const previewAudioRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const nativeCameraInputRef = useRef(null);
  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isRecording, isPaused, capturedPhoto]);

  // Clean up recording, camera & audio on unmount
  useEffect(() => {
    return () => {
      cleanupAudioRecording();
      closeLiveCamera();
      if (audioPlayerRef.current) audioPlayerRef.current.pause();
      if (previewAudioRef.current) previewAudioRef.current.pause();
    };
  }, []);



  // Helper: Encode raw Float32 audio samples into standard 16kHz mono 16-bit PCM WAV Blob
  const encodeWavBlob = (buffers, inputSampleRate = 48000) => {
    if (!buffers || buffers.length === 0) return null;

    let totalLength = 0;
    for (let i = 0; i < buffers.length; i++) {
      totalLength += buffers[i].length;
    }
    if (totalLength === 0) return null;

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (let i = 0; i < buffers.length; i++) {
      merged.set(buffers[i], offset);
      offset += buffers[i].length;
    }

    const targetSampleRate = 16000;
    let resampled;
    if (inputSampleRate === targetSampleRate) {
      resampled = merged;
    } else {
      const ratio = inputSampleRate / targetSampleRate;
      const newLen = Math.round(merged.length / ratio);
      resampled = new Float32Array(newLen);
      let offsetResult = 0;
      let offsetBuffer = 0;
      while (offsetResult < resampled.length) {
        const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
        let accum = 0;
        let count = 0;
        for (let i = offsetBuffer; i < nextOffsetBuffer && i < merged.length; i++) {
          accum += merged[i];
          count++;
        }
        resampled[offsetResult] = count > 0 ? accum / count : 0;
        offsetResult++;
        offsetBuffer = nextOffsetBuffer;
      }
    }

    const wavBuffer = new ArrayBuffer(44 + resampled.length * 2);
    const view = new DataView(wavBuffer);

    const writeString = (v, off, str) => {
      for (let i = 0; i < str.length; i++) v.setUint8(off + i, str.charCodeAt(i));
    };

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + resampled.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, targetSampleRate, true);
    view.setUint32(28, targetSampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, resampled.length * 2, true);

    let pcmOffset = 44;
    for (let i = 0; i < resampled.length; i++, pcmOffset += 2) {
      const s = Math.max(-1, Math.min(1, resampled[i]));
      view.setInt16(pcmOffset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: 'audio/wav' });
  };

  function cleanupAudioRecording() {
    isRecordingRef.current = false;
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (scriptProcessorRef.current) {
      try {
        scriptProcessorRef.current.disconnect();
      } catch {}
      scriptProcessorRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  }

  const formatTimer = (totalSeconds) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  // ----------------------------------------------------
  // Live Camera Functionality
  // ----------------------------------------------------
  const openLiveCamera = async (facing = cameraFacing) => {
    setErrorMsg(null);
    setIsCameraOpen(true);
    setCameraActive(false);

    try {
      if (cameraStreamRef.current) {
        cameraStreamRef.current.getTracks().forEach(t => t.stop());
        cameraStreamRef.current = null;
      }

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        // Fallback to native capture input if WebRTC camera is unavailable
        setIsCameraOpen(false);
        nativeCameraInputRef.current?.click();
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facing },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });

      cameraStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play().then(() => setCameraActive(true)).catch(() => setCameraActive(true));
        };
      } else {
        setCameraActive(true);
      }
    } catch (err) {
      console.warn("Live camera stream error, falling back to native camera:", err);
      closeLiveCamera();
      nativeCameraInputRef.current?.click();
    }
  };

  function closeLiveCamera() {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach(t => t.stop());
      cameraStreamRef.current = null;
    }
    setIsCameraOpen(false);
    setCameraActive(false);
  }

  const switchCameraFacing = () => {
    const nextFacing = cameraFacing === 'environment' ? 'user' : 'environment';
    setCameraFacing(nextFacing);
    openLiveCamera(nextFacing);
  };

  const snapLivePhoto = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');

    // If front camera, flip horizontally for mirror preview
    if (cameraFacing === 'user') {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], `crop_leaf_${Date.now()}.jpg`, { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);
      setCapturedPhoto({
        file: file,
        url: url,
        name: file.name,
      });
      closeLiveCamera();
    }, 'image/jpeg', 0.92);
  };

  // Fallback / Native Camera File Capture
  const handleNativeCameraCapture = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setCapturedPhoto({
      file: file,
      url: url,
      name: file.name,
    });
    e.target.value = '';
  };

  const removePhotoAttachment = () => {
    if (capturedPhoto?.url) {
      URL.revokeObjectURL(capturedPhoto.url);
    }
    setCapturedPhoto(null);
  };

  // Helper to generate finalized audio object (prefers pristine 16kHz WAV, falls back to MediaRecorder WebM)
  const generateFinalAudio = (durationSecs) => {
    const wavBlob = encodeWavBlob(pcmBuffersRef.current, audioCtxRef.current?.sampleRate || 48000);
    if (wavBlob && wavBlob.size > 44) {
      const file = new File([wavBlob], `voice_${Date.now()}.wav`, { type: 'audio/wav' });
      const url = URL.createObjectURL(wavBlob);
      return { file, blob: wavBlob, url, name: file.name, duration: formatTimer(durationSecs || 1) };
    }
    if (audioChunksRef.current.length > 0) {
      const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      const file = new File([blob], `voice_${Date.now()}.webm`, { type: 'audio/webm' });
      const url = URL.createObjectURL(blob);
      return { file, blob, url, name: file.name, duration: formatTimer(durationSecs || 1) };
    }
    return null;
  };

  // ----------------------------------------------------
  // Live Microphone Recording & Waveform Visualizer
  // ----------------------------------------------------
  const startRecording = async () => {
    setErrorMsg(null);
    setRecordedAudio(null);
    setIsPaused(false);
    pcmBuffersRef.current = [];
    audioChunksRef.current = [];

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setErrorMsg("Microphone is not supported in this browser. Please use Chrome/Edge or upload an audio file.");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      isRecordingRef.current = true;

      // 1. AudioContext for raw PCM capture (16kHz WAV) & waveform visualizer
      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
          const audioCtx = new AudioContextClass();
          audioCtxRef.current = audioCtx;
          const analyser = audioCtx.createAnalyser();
          analyser.fftSize = 64;
          const source = audioCtx.createMediaStreamSource(stream);
          source.connect(analyser);

          // ScriptProcessor for clean PCM recording
          const processor = audioCtx.createScriptProcessor(4096, 1, 1);
          processor.onaudioprocess = (e) => {
            if (isRecordingRef.current) {
              const channelData = e.inputBuffer.getChannelData(0);
              pcmBuffersRef.current.push(new Float32Array(channelData));
            }
          };
          source.connect(processor);
          processor.connect(audioCtx.destination);
          scriptProcessorRef.current = processor;

          const dataArray = new Uint8Array(analyser.frequencyBinCount);
          const updateWave = () => {
            if (!analyser) return;
            analyser.getByteFrequencyData(dataArray);
            const bars = [];
            const barCount = 32;
            for (let i = 0; i < barCount; i++) {
              const val = dataArray[i % dataArray.length] || 0;
              const barH = Math.max(4, Math.min(24, Math.round((val / 255) * 24)));
              bars.push(barH);
            }
            setWaveBars(bars);
            animFrameRef.current = requestAnimationFrame(updateWave);
          };
          animFrameRef.current = requestAnimationFrame(updateWave);
        }
      } catch (audioErr) {
        console.warn("AudioContext init warning:", audioErr);
      }

      // 2. MediaRecorder as secondary fallback
      let mimeType = 'audio/webm';
      if (typeof MediaRecorder !== 'undefined') {
        const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
        for (const type of types) {
          if (MediaRecorder.isTypeSupported(type)) {
            mimeType = type;
            break;
          }
        }
      }

      try {
        const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        mediaRecorderRef.current = mediaRecorder;
        mediaRecorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };
        mediaRecorder.start(200);
      } catch (mrErr) {
        console.warn("MediaRecorder start warning:", mrErr);
      }

      setIsRecording(true);
      setRecordingSeconds(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);

    } catch (err) {
      console.error("Microphone access error:", err);
      cleanupAudioRecording();
      setIsRecording(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMsg(t('mic_permission_denied'));
      } else {
        setErrorMsg("Unable to access microphone: " + err.message);
      }
    }
  };

  const pauseRecording = () => {
    isRecordingRef.current = false;
    const finalAudio = generateFinalAudio(recordingSeconds);
    cleanupAudioRecording();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch {}
    }
    if (finalAudio) {
      setRecordedAudio(finalAudio);
    }
    setIsRecording(false);
    setIsPaused(true);
  };

  const discardRecording = () => {
    cleanupAudioRecording();
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch {}
    }
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
    }
    if (recordedAudio?.url) {
      URL.revokeObjectURL(recordedAudio.url);
    }
    pcmBuffersRef.current = [];
    audioChunksRef.current = [];
    setIsRecording(false);
    setIsPaused(false);
    setRecordedAudio(null);
    setRecordingSeconds(0);
    setPreviewPlaying(false);
  };

  const togglePreviewPlayback = () => {
    if (!recordedAudio?.url) return;

    if (!previewAudioRef.current) {
      previewAudioRef.current = new Audio(recordedAudio.url);
      previewAudioRef.current.onended = () => setPreviewPlaying(false);
    }

    if (previewPlaying) {
      previewAudioRef.current.pause();
      setPreviewPlaying(false);
    } else {
      previewAudioRef.current.play().then(() => {
        setPreviewPlaying(true);
      }).catch(err => {
        console.warn("Preview play error:", err);
        setPreviewPlaying(false);
      });
    }
  };

  // Local File Upload Handler (audio attachment)
  const handleLocalFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('audio/') && !file.name.match(/\.(wav|mp3|m4a|webm|ogg|aac|flac)$/i)) {
      setErrorMsg("Please select a valid audio file (.wav, .mp3, .m4a, .webm, .ogg)");
      return;
    }

    setErrorMsg(null);
    const url = URL.createObjectURL(file);
    setRecordedAudio({
      file: file,
      blob: file,
      url: url,
      name: file.name,
      duration: 'Local File',
    });
    setIsPaused(true);
    e.target.value = '';
  };

  // Audio Playback for Chat Messages
  const playAudio = (id, audioSrc) => {
    if (activeAudioId === id && isPlayingAudio) {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      setIsPlayingAudio(false);
      return;
    }

    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
    }

    const audio = new Audio(audioSrc);
    audioPlayerRef.current = audio;
    setActiveAudioId(id);
    setIsPlayingAudio(true);

    audio.onended = () => {
      setIsPlayingAudio(false);
      setActiveAudioId(null);
    };

    audio.onerror = (e) => {
      console.error("Audio playback error:", e);
      setIsPlayingAudio(false);
      setActiveAudioId(null);
    };

    audio.play().catch(err => {
      console.warn("Audio play blocked:", err);
      setIsPlayingAudio(false);
    });
  };

  // ----------------------------------------------------
  // ----------------------------------------------------
  // Send Message (Text, Voice, or Live Camera Photo)
  // ----------------------------------------------------
  const handleSendVoice = async () => {
    if (isRecording) {
      isRecordingRef.current = false;
      const finalized = generateFinalAudio(recordingSeconds);
      cleanupAudioRecording();
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop(); } catch {}
      }
      setIsRecording(false);
      setIsPaused(false);
      if (finalized) {
        await processVoiceSubmission(finalized);
      }
      return;
    }

    if (recordedAudio) {
      const audioToSend = recordedAudio;
      setIsPaused(false);
      setRecordedAudio(null);
      await processVoiceSubmission(audioToSend);
    }
  };

  const processVoiceSubmission = async (audioObj) => {
    setErrorMsg(null);
    const userMessageId = Date.now();
    const newUserMessage = {
      id: userMessageId,
      type: 'user',
      text: input.trim() || (i18n.language === 'ta' ? '🎤 குரல் பதிவு' : '🎤 Voice Message'),
      isVoice: true,
      audioUrl: audioObj.url,
      fileName: audioObj.name,
      imageUrl: capturedPhoto?.url,
    };

    setMessages(prev => [...prev, newUserMessage]);
    setInput('');
    const photoToSend = capturedPhoto;
    setCapturedPhoto(null);
    setIsLoading(true);

    try {
      let data = null;

      // If photo is also attached, invoke the unified multimodal AgroNex Copilot workflow
      if (photoToSend) {
        const agentForm = new FormData();
        agentForm.append('audio', audioObj.file, audioObj.name || 'voice.webm');
        agentForm.append('image', photoToSend.file, photoToSend.name || 'leaf.jpg');
        agentForm.append('language', i18n.language || 'ta');

        const res = await fetch(`${apiUrl}/api/agent/run`, {
          method: 'POST',
          body: agentForm,
        });

        if (!res.ok) throw new Error(`Agent server error (${res.status}): ${res.statusText}`);
        const agentRes = await res.json();
        data = {
          reply: agentRes.recommendation,
          transcription: agentRes.transcription,
          detected_language: agentRes.language,
          audio_base64: agentRes.audio_base64,
          cropAnalysis: agentRes.crop_prediction,
          sprayAdvisory: agentRes.spray_advisory,
          explanation: agentRes.explanation
        };
      } else {
        const formData = new FormData();
        formData.append('file', audioObj.file, audioObj.name || 'voice.webm');
        formData.append('language', i18n.language || 'ta');
        if (initialContext) {
          formData.append('context', JSON.stringify(initialContext));
        }

        const res = await fetch(`${apiUrl}/api/assistant/voice`, {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          throw new Error(`Voice server error (${res.status}): ${res.statusText}`);
        }
        data = await res.json();
      }

      if (data.transcription) {
        setMessages(prev => prev.map(msg => 
          msg.id === userMessageId 
            ? { ...msg, transcription: data.transcription }
            : msg
        ));
      }

      const aiMessageId = Date.now() + 1;
      const newAiMessage = {
        id: aiMessageId,
        type: 'ai',
        text: data.reply,
        detectedLanguage: data.detected_language,
        audioBase64: data.audio_base64,
        cropAnalysis: data.cropAnalysis || null,
        sprayAdvisory: data.sprayAdvisory || null,
      };

      setMessages(prev => [...prev, newAiMessage]);

      if (data.audio_base64) {
        const audioUrl = `data:audio/wav;base64,${data.audio_base64}`;
        playAudio(aiMessageId, audioUrl);
      }

    } catch (err) {
      console.error("API error:", err);
      setErrorMsg("Failed to reach AgroNex voice assistant. Please check backend connection.");
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 2,
          type: 'ai',
          text: i18n.language === 'ta'
            ? "மன்னிக்கவும், குரலை செயலாக்குவதில் சிக்கல் ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்."
            : "Sorry, there was an issue processing your voice audio. Please try again.",
          isError: true,
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendText = async (e) => {
    if (e) e.preventDefault();
    const trimmedInput = input.trim();
    if (!trimmedInput && !capturedPhoto) return;

    setErrorMsg(null);
    const userMessageId = Date.now();
    const photoToSend = capturedPhoto;

    const newUserMessage = {
      id: userMessageId,
      type: 'user',
      text: trimmedInput || (i18n.language === 'ta' ? '📷 பயிர் புகைப்படம் பகுப்பாய்வு' : '📷 Crop Photo Analysis'),
      imageUrl: photoToSend?.url,
    };

    setMessages(prev => [...prev, newUserMessage]);
    setInput('');
    setCapturedPhoto(null);
    setIsLoading(true);

    try {
      let data = null;

      // 1. If photo is attached, execute the full multimodal AgroNex Copilot Agent
      if (photoToSend) {
        const agentForm = new FormData();
        agentForm.append('image', photoToSend.file, photoToSend.name || 'leaf.jpg');
        if (trimmedInput) agentForm.append('query', trimmedInput);
        agentForm.append('language', i18n.language || 'en');

        const agentRes = await fetch(`${apiUrl}/api/agent/run`, {
          method: 'POST',
          body: agentForm,
        });

        if (!agentRes.ok) throw new Error(`Agent error (${agentRes.status}): ${agentRes.statusText}`);
        const result = await agentRes.json();
        data = {
          reply: result.recommendation,
          audio_base64: result.audio_base64,
          cropAnalysis: result.crop_prediction,
          sprayAdvisory: result.spray_advisory,
          explanation: result.explanation
        };
      } else {
        // Standard chat with context grounding
        const res = await fetch(`${apiUrl}/api/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: trimmedInput,
            language: i18n.language || 'en',
            context: initialContext || null,
          }),
        });

        if (!res.ok) {
          throw new Error(`Chat error (${res.status}): ${res.statusText}`);
        }

        const result = await res.json();
        data = {
          reply: result.recommendation || result.reply,
          audio_base64: result.audio_base64,
          sprayAdvisory: result.spray_advisory || null,
          explanation: result.explanation || null
        };
      }

      const aiMessageId = Date.now() + 1;
      const newAiMessage = {
        id: aiMessageId,
        type: 'ai',
        text: data.reply,
        audioBase64: data.audio_base64,
        cropAnalysis: data.cropAnalysis || null,
        sprayAdvisory: data.sprayAdvisory || null,
        explanation: data.explanation || null,
      };


      setMessages(prev => [...prev, newAiMessage]);

      if (data.audio_base64) {
        const audioUrl = `data:audio/wav;base64,${data.audio_base64}`;
        playAudio(aiMessageId, audioUrl);
      }

    } catch (err) {
      console.error("API error:", err);
      setErrorMsg("Failed to reach AgroNex assistant.");
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 2,
          type: 'ai',
          text: i18n.language === 'ta'
            ? "மன்னிக்கவும், சேவையகத்துடன் தொடர்புகொள்வதில் சிக்கல் ஏற்பட்டது."
            : "Sorry, could not connect to AgroNex assistant. Please ensure backend is running.",
          isError: true,
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const sendQuickPrompt = (promptText) => {
    setInput(promptText);
  };

  const quickPrompts = i18n.language === 'ta' 
    ? [
        "மாதிரி என்ன அறிகுறிகளைக் கண்டறிந்தது?",
        "பயிருக்கு சிகிச்சையளிக்கும் முன் நான் எதைச் சரிபார்க்க வேண்டும்?",
        "இந்த முடிவை தமிழில் விளக்குங்கள்.",
        "வரவிருக்கும் வானிலை இந்த பயிரை எவ்வாறு பாதிக்கும்?",
        "நான் எப்போது KVK நிபுணரை அணுக வேண்டும்?"
      ]
    : [
        "What symptoms did the model detect?",
        "What should I check before treating this plant?",
        "Explain this result in Tamil.",
        "How might the upcoming weather affect this crop?",
        "When should I consult a KVK expert?"
      ];

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] md:h-[calc(100vh-100px)] bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden relative">
      {/* Header */}
      <div className="bg-agronex-deep text-white p-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
            <Bot size={24} />
          </div>
          <div>
            <h2 className="font-bold text-lg leading-tight flex items-center gap-2">
              {t('ask_ai_title')}
              <span className="text-xs bg-green-500/30 text-green-200 border border-green-400/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                <Sparkles size={10} /> Sarvam AI Voice & Vision
              </span>
            </h2>
            <p className="text-green-100 text-xs">{t('ask_ai_subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              const confirmMsg = i18n.language === 'ta' ? 'உரையாடல் வரலாற்றை அழிக்க விரும்புகிறீர்களா?' : 'Clear all conversation history?';
              if (!window.confirm(confirmMsg)) return;
              try {
                await fetch(`${apiUrl}/api/assistant/history`, { method: 'DELETE' });
                setMessages([{
                  id: Date.now(),
                  type: 'ai',
                  text: i18n.language === 'ta'
                    ? 'வணக்கம்! நான் அக்ரோநெக்ஸ் AI. உங்களின் புதிய கேள்விகளுக்கு உதவ தயாராக உள்ளேன்.'
                    : "Hello! I'm AgroNex AI. Ready to answer your agricultural questions."
                }]);
              } catch (e) {
                console.warn('Clear history failed:', e);
              }
            }}
            className="text-xs text-white/80 hover:text-white bg-white/10 hover:bg-white/20 p-2 rounded-xl border border-white/10 transition-colors cursor-pointer"
            title="Clear Chat History"
          >
            <Trash2 size={16} />
          </button>
          <div className="text-xs text-green-200 font-medium bg-black/20 px-3 py-1.5 rounded-full border border-white/10">
            {i18n.language === 'ta' ? 'தமிழ் / English' : 'English / தமிழ்'}
          </div>
        </div>
      </div>

      {/* Service Status Sub-bar */}
      <div className="bg-emerald-950/80 border-b border-emerald-900/60 px-4 py-1.5 text-[11px] text-emerald-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="font-semibold">{i18n.language === 'ta' ? 'வேளாண் சிந்தனை எஞ்சின்: நேரலை' : 'Agronomic Reasoner: Online'}</span>
        </div>
        <span className="opacity-80 text-[10px] hidden sm:inline">
          {i18n.language === 'ta' ? 'வானிலை & பயிர் விதிமுறைகளுடன் இணைக்கப்பட்டுள்ளது' : 'Grounded in meteorological rules & crop pathology'}
        </span>
      </div>

      {/* Error banner */}
      {errorMsg && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-xs text-amber-800 flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <AlertCircle size={14} className="text-amber-600 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-amber-700 hover:text-amber-900 font-bold ml-2">×</button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-grow p-4 overflow-y-auto space-y-4 bg-gray-50/50">
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'} gap-2`}>
            {msg.type === 'ai' && (
              <div className="w-8 h-8 bg-agronex-primary rounded-full flex items-center justify-center text-white flex-shrink-0 mt-1 shadow-sm">
                <Bot size={16} />
              </div>
            )}

            <div className={`max-w-[85%] md:max-w-[75%] p-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
              msg.type === 'user' 
                ? 'bg-agronex-primary text-white rounded-tr-sm' 
                : msg.isError 
                  ? 'bg-red-50 border border-red-200 text-red-700 rounded-tl-sm'
                  : 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm'
            }`}>
              {/* If user sent an image */}
              {msg.imageUrl && (
                <div className="mb-2.5 rounded-xl overflow-hidden border border-white/20 shadow-sm max-h-60 bg-black/5">
                  <img src={msg.imageUrl} alt="Crop Leaf" className="w-full h-auto object-cover max-h-56 rounded-xl" />
                </div>
              )}

              {/* User Voice Audio Player */}
              {msg.isVoice && msg.audioUrl && (
                <div className="mb-2 p-2 bg-white/15 rounded-xl border border-white/20 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => playAudio(`user-${msg.id}`, msg.audioUrl)}
                      className="w-8 h-8 rounded-full bg-white text-agronex-deep flex items-center justify-center hover:scale-105 transition-transform shadow-xs"
                      title="Play recorded voice"
                    >
                      {activeAudioId === `user-${msg.id}` && isPlayingAudio ? (
                        <Pause size={14} />
                      ) : (
                        <Play size={14} className="ml-0.5" />
                      )}
                    </button>
                    <div className="text-xs">
                      <div className="font-semibold">{t('voice_message')}</div>
                      <div className="opacity-80 text-[11px]">{msg.fileName || 'voice.webm'}</div>
                    </div>
                  </div>
                  <Mic size={16} className="opacity-70" />
                </div>
              )}

              {/* Show transcription if available */}
              {msg.transcription && (
                <div className="mb-1.5 text-xs bg-white/20 px-2.5 py-1.5 rounded-lg text-green-50 italic">
                  <span className="font-semibold not-italic">🗣️ {t('transcribed')}: </span>
                  "{msg.transcription}"
                </div>
              )}

              {/* Crop Analysis Badge if returned by AI */}
              {msg.cropAnalysis && (
                <div className="mb-2 p-3 bg-green-50 border border-green-200 rounded-xl text-gray-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-agronex-deep flex items-center gap-1.5 text-xs">
                      {msg.cropAnalysis.is_healthy ? (
                        <CheckCircle size={15} className="text-green-600" />
                      ) : (
                        <AlertTriangle size={15} className="text-amber-600" />
                      )}
                      {(msg.cropAnalysis.condition || '').replace(/_/g, ' ')}
                    </span>
                    <span className="text-[11px] font-semibold bg-green-100 text-green-800 px-2 py-0.5 rounded-full">
                      {(msg.cropAnalysis.confidence * 100).toFixed(0)}% Match
                    </span>
                  </div>

                  <div className="text-[11px] text-gray-600 flex items-center gap-3">
                    <span><strong>Status:</strong> {msg.cropAnalysis.status}</span>
                    <span>•</span>
                    <span><strong>Severity:</strong> {msg.cropAnalysis.severity || 'Moderate'}</span>
                  </div>
                </div>
              )}

              {/* Gemma 4 Multimodal Structured Explanation */}
              {msg.explanation && (
                <div className="mb-2.5 p-3.5 rounded-2xl bg-emerald-50/90 border border-emerald-200/80 text-xs text-gray-800 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-emerald-100 pb-1.5">
                    <span className="font-bold text-emerald-950 flex items-center gap-1.5">
                      <Sparkles size={13} className={msg.explanation.is_fallback ? "text-amber-600" : "text-emerald-600"} />
                      <span>{msg.explanation.is_fallback ? (msg.explanation.model_used || "Pathology Grounding Fallback") : (msg.explanation.model_used || "Gemma 4 Multimodal Assessment")}</span>
                    </span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full font-mono ${msg.explanation.is_fallback ? "bg-amber-100 text-amber-900 border border-amber-200" : "bg-emerald-100 text-emerald-800"}`}>
                      {msg.explanation.is_fallback ? "Offline Grounding" : "Explainable AI"}
                    </span>
                  </div>

                  {msg.explanation.summary && (
                    <p className="text-emerald-900 font-medium leading-relaxed bg-white/60 p-2 rounded-xl border border-emerald-100/60">
                      {msg.explanation.summary}
                    </p>
                  )}

                  {(msg.explanation.observed_symptoms || msg.explanation.observations) && (
                    <div className="space-y-0.5">
                      <strong className="text-emerald-950 font-semibold block">🔍 Symptoms & Observations:</strong>
                      <p className="text-gray-700 leading-relaxed">{msg.explanation.observed_symptoms || msg.explanation.observations}</p>
                    </div>
                  )}

                  {msg.explanation.possible_causes && (
                    <div className="space-y-0.5">
                      <strong className="text-emerald-950 font-semibold block">🧪 Suspected Pathological Causes:</strong>
                      <p className="text-gray-700 leading-relaxed">{msg.explanation.possible_causes}</p>
                    </div>
                  )}

                  {msg.explanation.alternative_explanations && msg.explanation.alternative_explanations.length > 0 && (
                    <div className="space-y-0.5">
                      <strong className="text-emerald-950 font-semibold block">🔄 Alternative Possibilities:</strong>
                      <p className="text-gray-600 text-[11px] leading-relaxed">
                        {msg.explanation.alternative_explanations.join(" • ")}
                      </p>
                    </div>
                  )}

                  {(msg.explanation.weather_influence || msg.explanation.weather_risk_factor) && (
                    <div className="space-y-0.5">
                      <strong className="text-emerald-950 font-semibold block">🌦️ Weather Factor:</strong>
                      <p className="text-gray-700 leading-relaxed">{msg.explanation.weather_influence || msg.explanation.weather_risk_factor}</p>
                    </div>
                  )}

                  {msg.explanation.recommended_next_steps && msg.explanation.recommended_next_steps.length > 0 && (
                    <div className="space-y-1">
                      <strong className="text-emerald-950 font-semibold block">✅ Recommended Next Steps:</strong>
                      <ul className="list-disc list-inside space-y-0.5 text-gray-700">
                        {msg.explanation.recommended_next_steps.map((st, i) => (
                          <li key={i}>{st}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {msg.explanation.prevention_guidance && msg.explanation.prevention_guidance.length > 0 && (
                    <div className="space-y-1">
                      <strong className="text-emerald-950 font-semibold block">🛡️ Prevention Guidance:</strong>
                      <ul className="list-disc list-inside space-y-0.5 text-gray-700 text-[11px]">
                        {msg.explanation.prevention_guidance.map((pv, i) => (
                          <li key={i}>{pv}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {(msg.explanation.uncertainty_and_limitations || msg.explanation.uncertainty_warnings) && (
                    <div className="p-2 bg-amber-50/90 rounded-xl border border-amber-200/60 text-[11px] text-amber-900 leading-relaxed">
                      <strong>⚠️ Agricultural Safety Notice:</strong> {msg.explanation.uncertainty_and_limitations || msg.explanation.uncertainty_warnings}
                    </div>
                  )}

                  {(msg.explanation.kvk_consultation_guidance || msg.explanation.expert_consultation_triggers) && (
                    <div className="p-2 bg-emerald-100/60 rounded-xl border border-emerald-200/60 text-[11px] text-emerald-900 leading-relaxed">
                      <strong>🏛️ KVK Expert Consultation:</strong> {msg.explanation.kvk_consultation_guidance || msg.explanation.expert_consultation_triggers}
                    </div>
                  )}
                </div>
              )}

              {/* Message text */}
              <div className="whitespace-pre-wrap">{msg.text}</div>


              {/* AI Voice playback button */}
              {msg.type === 'ai' && msg.audioBase64 && (
                <div className="mt-2.5 pt-2 border-t border-gray-100 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => playAudio(`ai-${msg.id}`, `data:audio/wav;base64,${msg.audioBase64}`)}
                    className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-agronex-primary/10 text-agronex-primary hover:bg-agronex-primary hover:text-white transition-all shadow-xs"
                  >
                    {activeAudioId === `ai-${msg.id}` && isPlayingAudio ? (
                      <>
                        <VolumeX size={14} />
                        <span>{t('pause') || 'Pause'}</span>
                        <span className="flex gap-0.5 items-end h-3 ml-1">
                          <span className="w-1 bg-current rounded-full animate-bounce h-2"></span>
                          <span className="w-1 bg-current rounded-full animate-bounce h-3 delay-100"></span>
                          <span className="w-1 bg-current rounded-full animate-bounce h-1.5 delay-200"></span>
                        </span>
                      </>
                    ) : (
                      <>
                        <Volume2 size={14} />
                        <span>{t('listen_voice')}</span>
                      </>
                    )}
                  </button>
                  {msg.detectedLanguage && (
                    <span className="text-[10px] text-gray-400 font-mono">
                      {msg.detectedLanguage}
                    </span>
                  )}
                </div>
              )}
            </div>

            {msg.type === 'user' && (
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-gray-600 flex-shrink-0 mt-1">
                <User size={16} />
              </div>
            )}
          </div>
        ))}

        {/* Loading state */}
        {isLoading && (
          <div className="flex justify-start gap-2 items-center">
            <div className="w-8 h-8 bg-agronex-primary rounded-full flex items-center justify-center text-white flex-shrink-0 animate-pulse">
              <Bot size={16} />
            </div>
            <div className="bg-white border border-gray-100 p-3 rounded-2xl rounded-tl-sm text-xs text-gray-500 shadow-sm flex items-center gap-2">
              <Loader2 size={16} className="animate-spin text-agronex-primary" />
              <span>{t('listening_ai')}</span>
            </div>
          </div>
        )}

        {/* Quick prompt suggestions when only welcome message */}
        {messages.length === 1 && !isRecording && !isPaused && (
          <div className="pt-2">
            <p className="text-xs text-gray-400 mb-2 font-medium">💡 Try asking, speaking, or snapping a crop photo:</p>
            <div className="flex flex-wrap gap-2">
              {quickPrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => sendQuickPrompt(prompt)}
                  className="text-xs text-gray-600 bg-white border border-gray-200 hover:border-agronex-primary hover:text-agronex-primary px-3 py-1.5 rounded-full transition-colors text-left"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Live Camera Viewfinder Overlay Modal */}
      {isCameraOpen && (
        <div className="absolute inset-0 z-50 bg-black/95 flex flex-col justify-between p-4 animate-fadeIn">
          {/* Top Bar: Close & Switch Camera */}
          <div className="flex items-center justify-between text-white z-10">
            <button
              type="button"
              onClick={closeLiveCamera}
              className="p-2.5 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
              title="Close camera"
            >
              <X size={20} />
            </button>
            <span className="text-xs font-semibold bg-white/20 px-3 py-1 rounded-full">
              {i18n.language === 'ta' ? 'பயிர் இலையை மையத்தில் வைக்கவும்' : 'Focus leaf in camera frame'}
            </span>
            <button
              type="button"
              onClick={switchCameraFacing}
              className="p-2.5 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
              title="Flip camera"
            >
              <RefreshCw size={20} />
            </button>
          </div>

          {/* Camera Viewfinder Video Feed */}
          <div className="flex-grow flex items-center justify-center relative overflow-hidden my-2 rounded-2xl border-2 border-white/30 bg-black">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />
            {/* Camera Initializing Spinner */}
            {!cameraActive && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 text-white text-xs">
                <Loader2 size={24} className="animate-spin text-emerald-400 mb-2" />
                <span>Starting camera...</span>
              </div>
            )}
            {/* Viewfinder Target Guide Overlay */}
            <div className="absolute inset-8 border-2 border-dashed border-white/50 rounded-2xl pointer-events-none flex items-center justify-center">
              <span className="text-[11px] text-white/80 bg-black/40 px-3 py-1 rounded-full">
                🌿 {t('take_photo')}
              </span>
            </div>
          </div>

          {/* Bottom Bar: Shutter Button */}
          <div className="flex items-center justify-around py-3 z-10">
            <button
              type="button"
              onClick={() => nativeCameraInputRef.current?.click()}
              className="text-xs text-gray-300 hover:text-white flex flex-col items-center gap-1"
            >
              <ImageIcon size={22} />
              <span>{t('upload_image')}</span>
            </button>

            {/* Big Shutter Button */}
            <button
              type="button"
              onClick={snapLivePhoto}
              className="w-18 h-18 rounded-full border-4 border-white bg-agronex-primary hover:scale-105 active:scale-95 flex items-center justify-center shadow-2xl transition-transform"
              title="Snap Photo"
            >
              <div className="w-14 h-14 rounded-full bg-white/90"></div>
            </button>

            <button
              type="button"
              onClick={closeLiveCamera}
              className="text-xs text-gray-300 hover:text-white flex flex-col items-center gap-1"
            >
              <X size={22} />
              <span>{t('cancel_recording')}</span>
            </button>
          </div>
        </div>
      )}

      {/* Input container: Switches to WhatsApp-style Voice Bar when recording or paused */}
      <div className="p-3 bg-white border-t border-gray-100">
        {/* Attached Photo Preview (Saved until entered and sent) */}
        {capturedPhoto && !isRecording && (
          <div className="mb-2 p-2 bg-green-50 border border-green-200 rounded-2xl flex items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="w-12 h-12 rounded-xl overflow-hidden bg-black/10 flex-shrink-0 border border-green-300">
                <img src={capturedPhoto.url} alt="Crop Thumbnail" className="w-full h-full object-cover" />
              </div>
              <div className="overflow-hidden">
                <div className="text-xs font-bold text-agronex-deep truncate">
                  {capturedPhoto.name}
                </div>
                <div className="text-[11px] text-green-700 flex items-center gap-1 font-medium">
                  <CheckCircle size={12} />
                  <span>{i18n.language === 'ta' ? 'பயிர் புகைப்படம் இணைக்கப்பட்டது' : 'Crop leaf photo ready'}</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={removePhotoAttachment}
              className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors flex-shrink-0"
              title="Remove photo"
            >
              <X size={18} />
            </button>
          </div>
        )}

        {isRecording || isPaused ? (
          /* ======================================================== */
          /* WhatsApp / Telegram Style Voice Recording Capsule Bar   */
          /* [Trash]  [Red Dot] 0:04  |||||||||||||||||||  [Pause] [>] */
          /* ======================================================== */
          <div className="bg-[#18222d] text-white rounded-full p-2 px-4 flex items-center justify-between gap-3 shadow-md animate-fadeIn">
            {/* 1. Trash Can Icon (Left) */}
            <button
              type="button"
              onClick={discardRecording}
              className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-white/10 rounded-full transition-colors flex-shrink-0"
              title="Delete recording"
            >
              <Trash2 size={20} />
            </button>

            {/* 2. Red Pulsing Dot + Live Timer */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`w-2.5 h-2.5 rounded-full ${isPaused ? 'bg-amber-400' : 'bg-[#f87171] animate-ping'}`} />
              <span className="font-mono text-sm font-semibold text-white tracking-wide">
                {formatTimer(recordingSeconds)}
              </span>
            </div>

            {/* 3. Audio Waveform Visualizer (Center) */}
            <div className="flex-grow flex items-center justify-center gap-[2.5px] h-7 px-2 overflow-hidden">
              {waveBars.map((height, i) => (
                <span
                  key={i}
                  style={{ height: `${height}px` }}
                  className={`w-[2.5px] rounded-full transition-all duration-75 ${
                    isPaused ? 'bg-gray-500' : 'bg-gray-300'
                  }`}
                />
              ))}
            </div>

            {/* 4. Pause / Stop / Play Preview Toggle */}
            {isRecording ? (
              <button
                type="button"
                onClick={pauseRecording}
                className="p-1.5 flex items-center justify-center gap-1 hover:opacity-80 transition-opacity flex-shrink-0"
                title="Pause & review recording"
              >
                <span className="w-1.5 h-5 bg-[#f87171] rounded-full" />
                <span className="w-1.5 h-5 bg-[#f87171] rounded-full" />
              </button>
            ) : (
              <button
                type="button"
                onClick={togglePreviewPlayback}
                className="p-1.5 text-[#f87171] hover:opacity-80 transition-opacity flex-shrink-0"
                title={previewPlaying ? "Pause preview" : "Listen to preview"}
              >
                {previewPlaying ? <Pause size={20} className="fill-[#f87171]" /> : <Play size={20} className="fill-[#f87171]" />}
              </button>
            )}

            {/* 5. Green Circular Send Button (Right) */}
            <button
              type="button"
              onClick={handleSendVoice}
              disabled={isLoading}
              className="w-10 h-10 rounded-full bg-[#00a884] hover:bg-[#008f6f] active:scale-95 text-black flex items-center justify-center shadow-lg transition-transform flex-shrink-0"
              title="Send voice query"
            >
              <Send size={18} className="text-black ml-0.5" />
            </button>
          </div>
        ) : (
          /* ======================================================== */
          /* Normal Message Input Form                                */
          /* ======================================================== */
          <form onSubmit={handleSendText} className="flex gap-2 bg-gray-100 p-1 pl-3 rounded-full items-center">
            {/* Hidden file input for audio attachment */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleLocalFileUpload}
              accept="audio/*,.wav,.mp3,.m4a,.webm,.ogg"
              className="hidden"
            />

            {/* Hidden file input for native device camera fallback */}
            <input
              type="file"
              ref={nativeCameraInputRef}
              onChange={handleNativeCameraCapture}
              accept="image/*"
              capture="environment"
              className="hidden"
            />

            {/* 1. Attachment Button (Audio / File) */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-gray-500 hover:text-agronex-primary transition-colors rounded-full hover:bg-white/80"
              title={t('upload_audio')}
            >
              <Paperclip size={18} />
            </button>

            {/* 2. Live Camera Button (Take Photo) */}
            <button
              type="button"
              onClick={() => openLiveCamera('environment')}
              className="p-2 text-gray-500 hover:text-agronex-primary transition-colors rounded-full hover:bg-white/80"
              title={t('take_photo')}
            >
              <Camera size={19} />
            </button>

            {/* 3. Text input */}
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={capturedPhoto ? (i18n.language === 'ta' ? "புகைப்படம் தயாராக உள்ளது. கேள்வி கேட்கவும்..." : "Photo ready. Ask a question or press Send...") : t('type_message')}
              disabled={isLoading}
              className="flex-grow bg-transparent border-none outline-none text-gray-700 text-sm placeholder-gray-400"
            />

            {/* 4. Live Mic button */}
            <button 
              type="button" 
              onClick={startRecording}
              disabled={isLoading}
              className="p-2 text-gray-500 hover:text-red-600 transition-colors rounded-full hover:bg-white/80"
              title={i18n.language === 'ta' ? "பேச மைக் கிளிக் செய்க" : "Click to speak via microphone"}
            >
              <Mic size={20} />
            </button>

            {/* 5. Submit / Send button */}
            <button 
              type="submit" 
              disabled={isLoading || (!input.trim() && !capturedPhoto)}
              className={`p-2 rounded-full transition-all shadow-xs ${
                (!input.trim() && !capturedPhoto) || isLoading
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-agronex-primary text-white hover:bg-agronex-deep hover:scale-105'
              }`}
              title="Send message"
            >
              <Send size={18} className="ml-0.5" />
            </button>
          </form>
        )}
      </div>
    </div>
  );
}



