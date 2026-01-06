// Sistema de Celebração para Checklists
// Confetes + Som (Ding) + Vibração

// Som "Ding" cristalino usando AudioContext (tom alto, estilo notificação premium)
let audioContext = null;

// Função para criar e tocar som "ding" cristalino (ping de sucesso premium)
function playDing() {
    try {
        // Primeiro tenta usar Base64 de um som cristalino real
        const base64Audio = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIGWi77+efTRAMUKfj8LZjHAY4kdfyzHksBSR3x/DdkEAKFF606euoVRQKRp/g8r5sIQUrgc7y2Yk2CBlou+/nn00QDFCn4/C2YxwGOJHX8sx5LAUkd8fw3ZBACg==';
        const audio = new Audio(base64Audio);
        audio.volume = 0.7;
        audio.play().catch(() => {
            // Se Base64 falhar, usa AudioContext como fallback
            fallbackAudioContext();
        });
    } catch (e) {
        console.log('Erro ao tocar som Base64:', e);
        fallbackAudioContext();
    }
}

// Fallback: Gera som usando AudioContext
function fallbackAudioContext() {
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        // Frequência mais alta (1500Hz) para som mais cristalino
        const frequency = 1500;
        const duration = 0.2; // 200ms - mais curto e preciso
        const sampleRate = audioContext.sampleRate;
        const numSamples = Math.floor(duration * sampleRate);
        
        const buffer = audioContext.createBuffer(1, numSamples, sampleRate);
        const data = buffer.getChannelData(0);
        
        // Gera onda senoidal com envelope mais agressivo para "ping" nítido
        for (let i = 0; i < numSamples; i++) {
            const t = i / sampleRate;
            // Envelope exponencial mais rápido para "ping" nítido
            const envelope = Math.exp(-t * 15);
            // Onda senoidal com frequência alta
            data[i] = Math.sin(2 * Math.PI * frequency * t) * envelope * 0.6;
        }
        
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start(0);
    } catch (e) {
        console.log('Erro no fallback AudioContext:', e);
    }
}

// Função para vibrar (se suportado)
function vibrate() {
    if ('vibrate' in navigator) {
        navigator.vibrate(50); // 50ms de vibração suave
    }
}

// Função para disparar confetes
function celebrate() {
    if (typeof confetti !== 'undefined') {
        confetti({
            particleCount: 150,
            spread: 70,
            origin: { y: 0.6 },
            colors: ['#F83531', '#FFFFFF', '#22C55E']
        });
    }
}

// Função para celebrar conclusão (chama todas as funções)
function celebrateCompletion() {
    celebrate(); // Confetes
    playDing(); // Som
    vibrate(); // Vibração
}

