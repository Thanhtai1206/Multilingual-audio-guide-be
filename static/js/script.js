document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;
    const locationInput = document.getElementById('location');
    const durationInput = document.getElementById('duration');
    const durationVal = document.getElementById('duration-val');
    const generateBtn = document.getElementById('generate-btn');
    const chips = document.querySelectorAll('.chip');
    const resultSection = document.getElementById('result-section');
    const tourContent = document.getElementById('tour-content');
    const resultLocation = document.getElementById('result-location');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingProgress = document.getElementById('loading-progress');
    const loadingText = document.getElementById('loading-text');
    const playBtn = document.getElementById('play-btn');
    const stopBtn = document.getElementById('stop-btn');
    const downloadLink = document.getElementById('download-link');
    const audioPlayer = document.getElementById('audio-player');
    const suggestLinks = document.querySelectorAll('.suggest-link');
    const sidebarSteps = document.querySelectorAll('.progress-sidebar .step');
    const audioProgress = document.getElementById('audio-progress');
    const currentTimeEl = document.getElementById('current-time');
    const totalTimeEl = document.getElementById('total-time');
    const etaSec = document.getElementById('eta-sec');

    // Sidebar Progress Control
    function updateSidebar(stepNumber) {
        document.querySelectorAll('.progress-sidebar .step').forEach(step => {
            const num = parseInt(step.dataset.step);
            step.classList.remove('active', 'completed');
            if (num < stepNumber) step.classList.add('completed');
            if (num === stepNumber) step.classList.add('active');
        });
    }

    updateSidebar(1); // Start at step 1

    // Duration Slider
    durationInput.addEventListener('input', (e) => {
        const mins = e.target.value;
        const words = mins * 150;
        durationVal.textContent = `${mins} mins (~${words} words)`;
    });

    // Chips Selection
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            chip.classList.toggle('active');
        });
    });

    // Generate Tour
    generateBtn.addEventListener('click', async () => {
        const location = locationInput.value.trim();
        const duration = parseInt(durationInput.value);
        const interests = Array.from(document.querySelectorAll('.chip.active')).map(c => c.dataset.value);

        if (!location) {
            alert('Please enter a location or landmark!');
            return;
        }

        if (interests.length === 0) {
            alert('Please select at least one interest!');
            return;
        }

        // Show Overlay & Reset
        loadingOverlay.classList.remove('hidden');
        resultSection.classList.add('hidden');
        stopAudio();

        // ETA Countdown
        let timeLeft = 15;
        etaSec.textContent = timeLeft;
        const etaInterval = setInterval(() => {
            if (timeLeft > 0) {
                timeLeft--;
                etaSec.textContent = timeLeft;
            }
        }, 1000);

        // Progress Simulation for Better UX
        let progress = 0;
        const progressInterval = setInterval(() => {
            if (progress < 90) {
                progress += Math.random() * 2;
                loadingProgress.style.width = `${progress}%`;

                if (progress > 20 && progress < 50) {
                    loadingText.textContent = "Planning your unique itinerary...";
                    updateSidebar(2);
                } else if (progress >= 50 && progress < 80) {
                    loadingText.textContent = "Researching local stories and secrets...";
                    updateSidebar(3);
                } else if (progress >= 80) {
                    loadingText.textContent = "Finalizing your audio narration...";
                    updateSidebar(4);
                }
            }
        }, 500);

        try {
            console.log('Starting tour generation...', { location, duration, interests });
            const response = await fetch('/api/generate-tour', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ location, duration, interests })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error('Backend Error Response:', errorData);
                throw new Error(errorData.detail || 'Failed to generate tour');
            }

            const data = await response.json();
            console.log('Received generation data:', data);

            clearInterval(progressInterval);
            clearInterval(etaInterval);
            loadingProgress.style.width = '100%';
            loadingText.textContent = "Tour ready!";
            updateSidebar(5);

            setTimeout(() => {
                resultLocation.textContent = `Your Tour of ${data.location}`;
                tourContent.innerHTML = marked.parse(data.content);

                if (data.audio_url) {
                    audioPlayer.src = data.audio_url;
                    downloadLink.href = data.audio_url;
                    downloadLink.classList.remove('hidden');
                    downloadLink.download = `${data.location.replace(/\s+/g, '_')}_tour.mp3`;
                } else {
                    downloadLink.classList.add('hidden');
                }

                resultSection.classList.remove('hidden');
                loadingOverlay.classList.add('hidden');
                resultSection.scrollIntoView({ behavior: 'smooth' });
            }, 500);

        } catch (error) {
            clearInterval(progressInterval);
            clearInterval(etaInterval);
            console.error('Generation Flow Error:', error);
            alert(`Error: ${error.message}`);
            loadingOverlay.classList.add('hidden');
            updateSidebar(1);
        }
    });

    // Audio Logic
    playBtn.addEventListener('click', () => {
        audioPlayer.play();
    });

    stopBtn.addEventListener('click', () => {
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
    });

    audioPlayer.addEventListener('play', () => {
        playBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');
    });

    audioPlayer.addEventListener('pause', () => {
        playBtn.classList.remove('hidden');
        stopBtn.classList.add('hidden');
    });

    audioPlayer.addEventListener('ended', () => {
        playBtn.classList.remove('hidden');
        stopBtn.classList.add('hidden');
        audioProgress.value = 0;
    });

    // Real-time Audio Progress
    audioPlayer.addEventListener('timeupdate', () => {
        if (!isNaN(audioPlayer.duration)) {
            const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100;
            audioProgress.value = progress;
            currentTimeEl.textContent = formatTime(audioPlayer.currentTime);
            totalTimeEl.textContent = formatTime(audioPlayer.duration);
        }
    });

    // Seekable progress bar
    audioProgress.addEventListener('input', (e) => {
        const seekTime = (e.target.value / 100) * audioPlayer.duration;
        audioPlayer.currentTime = seekTime;
    });

    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    }

    function stopAudio() {
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        playBtn.classList.remove('hidden');
        stopBtn.classList.add('hidden');
    }
});
