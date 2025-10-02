import React, { useState } from 'react';
import { db } from '../firebaseConfig';
import { collection, addDoc, serverTimestamp } from 'firebase/firestore';

export default function StudySession() {
  const [subject, setSubject] = useState('');
  const [duration, setDuration] = useState(0);

  const startSession = async () => {
    try {
      await addDoc(collection(db, 'sessions'), {
        subject,
        duration,
        timestamp: serverTimestamp()
      });
      alert('Session Saved!');
    } catch (e) {
      console.error('Error adding document: ', e);
    }
  };

  return (
    <div>
      <h2>Track Study Session</h2>
      <input placeholder="Subject" value={subject} onChange={e => setSubject(e.target.value)} />
      <input type="number" placeholder="Duration (minutes)" value={duration} onChange={e => setDuration(e.target.value)} />
      <button onClick={startSession}>Save Session</button>
    </div>
  );
}
