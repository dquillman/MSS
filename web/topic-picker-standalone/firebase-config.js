// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, EmailAuthProvider } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { getStorage } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-storage.js";

const firebaseConfig = {
    apiKey: "AIzaSyDMuClZTkr7nxjSzEPkbUOwXgvhZXU_A4Y",
    authDomain: "mss-video-creator-app.firebaseapp.com",
    projectId: "mss-video-creator-app",
    storageBucket: "mss-video-creator-app.firebasestorage.app",
    messagingSenderId: "191944095586",
    appId: "1:191944095586:web:5092b345c62f27fcbede3b"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const storage = getStorage(app);

export { app, auth, db, storage, GoogleAuthProvider, EmailAuthProvider };
