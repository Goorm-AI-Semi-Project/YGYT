import axios from 'axios';

// FastAPI 백엔드 URL
// Docker 환경: 컨테이너 이름 사용, 로컬 개발: localhost 사용
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Axios 인스턴스 생성
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 채팅 세션 초기화 - AI가 첫 인사
 * @param {string} language - 언어 코드 (ko, en, ja, zh)
 */
export const initChat = async (language = 'ko') => {
  try {
    const response = await apiClient.post('/api/chat/init', {
      language
    });
    return response.data;
  } catch (error) {
    console.error('채팅 초기화 실패:', error);
    throw error;
  }
};

/**
 * 사용자 메시지 전송
 * @param {string} message - 사용자 메시지
 * @param {Array} llmHistory - 대화 히스토리
 * @param {Object} profile - 현재 프로필
 */
export const sendChatMessage = async (message, llmHistory, profile) => {
  try {
    const response = await apiClient.post('/api/chat/message', {
      message,
      llm_history: llmHistory,
      profile,
    });
    return response.data;
  } catch (error) {
    console.error('메시지 전송 실패:', error);
    throw error;
  }
};

/**
 * 프로필 기반 맞춤 추천 생성
 * @param {Object} profile - 사용자 프로필 (13개 항목)
 * @param {number} topK - 반환할 결과 수
 * @param {Object} weights - 가중치 설정 (선택적)
 */
export const generateRecommendations = async (profile, topK = 10, weights = null) => {
  try {
    const requestData = {
      profile,
      top_k: topK,
    };

    // 가중치가 제공되면 추가
    if (weights) {
      requestData.weights = weights;
    }

    const response = await apiClient.post('/api/recommendations/generate', requestData);
    return response.data;
  } catch (error) {
    console.error('추천 생성 실패:', error);
    throw error;
  }
};

/**
 * 식당 상세 정보 조회
 * @param {string} restaurantId - 식당 ID
 */
export const getRestaurantDetail = async (restaurantId) => {
  try {
    const response = await apiClient.get(`/api/restaurants/${restaurantId}`);
    return response.data;
  } catch (error) {
    console.error('식당 정보 조회 실패:', error);
    throw error;
  }
};

/**
 * 텍스트 번역
 * @param {string} text - 번역할 텍스트
 * @param {string} targetLanguage - 목표 언어 (en, ja, zh)
 */
export const translateText = async (text, targetLanguage) => {
  try {
    const response = await apiClient.post('/api/translate', {
      text,
      target_language: targetLanguage,
    });
    return response.data;
  } catch (error) {
    console.error('번역 실패:', error);
    throw error;
  }
};

/**
 * 배치 텍스트 번역
 * @param {Array<string>} texts - 번역할 텍스트 배열
 * @param {string} targetLanguage - 목표 언어 (en, ja, zh)
 */
export const batchTranslateText = async (texts, targetLanguage) => {
  try {
    const response = await apiClient.post('/api/translate/batch', {
      texts,
      target_language: targetLanguage,
    });
    return response.data;
  } catch (error) {
    console.error('배치 번역 실패:', error);
    throw error;
  }
};

export default apiClient;
