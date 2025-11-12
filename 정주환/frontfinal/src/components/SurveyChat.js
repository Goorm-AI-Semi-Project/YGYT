import { useState, useEffect, useRef } from 'react';
import { FaRobot, FaUser, FaPaperPlane } from 'react-icons/fa';
import { IoSparkles } from 'react-icons/io5';
import { initChat, sendChatMessage } from '../services/api';
import './SurveyChat.css';

function SurveyChat({ onSurveyComplete }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [llmHistory, setLlmHistory] = useState([]);
  const [profile, setProfile] = useState({});
  const [isCompleted, setIsCompleted] = useState(false);
  const messagesEndRef = useRef(null);

  // 자동 스크롤
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 컴포넌트 마운트 시 초기화
  useEffect(() => {
    initializeChat();
  }, []);

  const initializeChat = async () => {
    setLoading(true);
    try {
      const response = await initChat();
      setMessages([{ role: 'assistant', content: response.bot_message }]);
      setLlmHistory([{ role: 'assistant', content: response.bot_message }]);
      setProfile(response.profile);
    } catch (error) {
      setMessages([
        {
          role: 'assistant',
          content: '죄송합니다. 서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage = inputValue.trim();
    setInputValue('');

    // 사용자 메시지 추가
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await sendChatMessage(userMessage, llmHistory, profile);

      // AI 응답 추가
      setMessages((prev) => [...prev, { role: 'assistant', content: response.bot_message }]);
      setLlmHistory([...llmHistory,
        { role: 'user', content: userMessage },
        { role: 'assistant', content: response.bot_message }
      ]);
      setProfile(response.profile);
      setIsCompleted(response.is_completed);

      // 설문 완료 시 부모 컴포넌트에 알림
      if (response.is_completed) {
        setTimeout(() => {
          onSurveyComplete(response.profile);
        }, 2000);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 프로필 진행률 계산
  const getProfileProgress = () => {
    const totalFields = 13;
    const filledFields = Object.values(profile).filter((v) => v !== null && v !== undefined).length;
    return Math.round((filledFields / totalFields) * 100);
  };

  return (
    <div className="survey-chat-container">
      <div className="survey-header">
        <div className="header-content">
          <IoSparkles className="header-sparkle" />
          <h2>맞춤 식당 추천을 위한 간단한 설문</h2>
        </div>
        <div className="progress-section">
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: `${getProfileProgress()}%` }}></div>
          </div>
          <p className="progress-text">{getProfileProgress()}% 완료</p>
        </div>
      </div>

      <div className="messages-container">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === 'assistant' ? <FaRobot /> : <FaUser />}
            </div>
            <div className="message-bubble">
              <p>{msg.content}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-avatar">
              <FaRobot />
            </div>
            <div className="message-bubble loading">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {!isCompleted && (
        <div className="input-container">
          <input
            type="text"
            className="message-input"
            placeholder="답변을 입력하세요..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={loading}
          />
          <button className="send-button" onClick={handleSendMessage} disabled={loading || !inputValue.trim()}>
            <FaPaperPlane className="send-icon" />
            <span>전송</span>
          </button>
        </div>
      )}

      {isCompleted && (
        <div className="completion-message">
          <IoSparkles className="completion-icon" />
          <p>설문이 완료되었습니다! 맞춤 추천을 생성하는 중...</p>
        </div>
      )}
    </div>
  );
}

export default SurveyChat;
