import axios from 'axios';

// FastAPI 백엔드 URL
const API_BASE_URL = 'http://127.0.0.1:8000';

// Axios 인스턴스 생성
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 채팅 세션 초기화 - AI가 첫 인사
 */
export const initChat = async () => {
  try {
    const response = await apiClient.post('/api/chat/init');
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
 */
export const generateRecommendations = async (profile, topK = 10) => {
  try {
    const response = await apiClient.post('/api/recommendations/generate', {
      profile,
      top_k: topK,
    });
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

export default apiClient;
