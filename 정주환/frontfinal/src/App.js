import { useState } from 'react';
import { IoRestaurantSharp, IoSparkles } from 'react-icons/io5';
import { MdRestaurant, MdTrendingUp } from 'react-icons/md';
import { FaRoute, FaUserCircle, FaBrain, FaMapMarkedAlt } from 'react-icons/fa';
import { BiSolidFoodMenu } from 'react-icons/bi';
import SurveyChat from './components/SurveyChat';
import RestaurantList from './components/RestaurantList';
import RestaurantModal from './components/RestaurantModal';
import WeightsControl from './components/WeightsControl';
import { generateRecommendations } from './services/api';
import './App.css';

function App() {
  const [currentStep, setCurrentStep] = useState('survey'); // 'survey' | 'recommendations'
  const [userProfile, setUserProfile] = useState(null);
  const [restaurants, setRestaurants] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRestaurant, setSelectedRestaurant] = useState(null);
  const [topK, setTopK] = useState(10);
  const [weights, setWeights] = useState({
    travel: 0.4,
    friendliness: 0.3,
    quality: 0.2,
    price: 0.1
  });

  const handleSurveyComplete = async (profile) => {
    console.log('설문 완료! 프로필:', profile);
    setUserProfile(profile);
    setCurrentStep('loading');

    // 추천 생성
    await loadRecommendations(profile, topK, weights);
  };

  const loadRecommendations = async (profile, k = 10, currentWeights = null) => {
    setLoading(true);
    setError(null);

    try {
      const response = await generateRecommendations(profile, k, currentWeights);
      setRestaurants(response.restaurants);
      setCurrentStep('recommendations');
    } catch (err) {
      setError('추천 생성 중 오류가 발생했습니다. 다시 시도해주세요.');
      console.error('Recommendation error:', err);
      setCurrentStep('error');
    } finally {
      setLoading(false);
    }
  };

  const handleTopKChange = async (newTopK) => {
    setTopK(newTopK);
    if (userProfile) {
      await loadRecommendations(userProfile, newTopK, weights);
    }
  };

  const handleWeightsChange = async (newWeights) => {
    setWeights(newWeights);
    if (userProfile && currentStep === 'recommendations') {
      await loadRecommendations(userProfile, topK, newWeights);
    }
  };

  const handleWeightsReset = async () => {
    if (userProfile && currentStep === 'recommendations') {
      await loadRecommendations(userProfile, topK, {
        travel: 0.4,
        friendliness: 0.3,
        quality: 0.2,
        price: 0.1
      });
    }
  };

  const handleRestaurantClick = (restaurant) => {
    setSelectedRestaurant(restaurant);
  };

  const closeModal = () => {
    setSelectedRestaurant(null);
  };

  const handleRetry = () => {
    setCurrentStep('survey');
    setUserProfile(null);
    setRestaurants([]);
    setError(null);
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <div className="logo-section">
            <IoRestaurantSharp className="logo-icon" />
            <div>
              <h1 className="app-title">길따라 맛따라</h1>
              <p className="app-subtitle">AI 기반 맞춤 식당 추천 서비스</p>
            </div>
          </div>
          {currentStep === 'recommendations' && userProfile && (
            <div className="user-info">
              <FaUserCircle className="user-avatar" />
              <span>{userProfile.name}님</span>
            </div>
          )}
        </div>
      </header>

      <main className="main-content">
        {currentStep === 'survey' && (
          <>
            <div className="hero-banner">
              <div className="hero-content">
                <div className="hero-icon">🍽️</div>
                <h1>AI가 찾아주는 나만의 맛집</h1>
                <p>간단한 설문으로 당신의 취향에 딱 맞는 식당을 추천받으세요</p>
                <div className="hero-features">
                  <div className="feature-item">
                    <div className="feature-icon"><FaBrain /></div>
                    <span>AI 맞춤 분석</span>
                  </div>
                  <div className="feature-item">
                    <div className="feature-icon"><FaMapMarkedAlt /></div>
                    <span>위치 기반 추천</span>
                  </div>
                  <div className="feature-item">
                    <div className="feature-icon"><BiSolidFoodMenu /></div>
                    <span>다양한 메뉴</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="content-wrapper">
              <SurveyChat onSurveyComplete={handleSurveyComplete} />
            </div>
          </>
        )}

        {currentStep === 'loading' && (
          <div className="content-wrapper">
            <div className="loading-recommendations">
              <div className="loading-content">
                <div className="spinner-large"></div>
                <h2><IoSparkles className="inline-icon" /> 맞춤 추천을 생성하는 중...</h2>
                <div className="loading-steps">
                  <p><MdRestaurant className="step-icon" /> 1단계: RAG 검색으로 후보군 생성 중</p>
                  <p><FaRoute className="step-icon" /> 2단계: 사용자 위치 기반 정밀 스코어링 중</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === 'recommendations' && (
          <div className="recommendations-section">
            <div className="recommendations-header">
              <div className="header-left">
                <IoSparkles className="header-icon sparkle" />
                <h2>{userProfile?.name}님을 위한 맞춤 추천</h2>
              </div>
              <div className="topk-control">
                <MdTrendingUp className="control-icon" />
                <label>표시 개수</label>
                <select value={topK} onChange={(e) => handleTopKChange(Number(e.target.value))}>
                  <option value={5}>5개</option>
                  <option value={10}>10개</option>
                  <option value={15}>15개</option>
                  <option value={20}>20개</option>
                </select>
              </div>
            </div>
            <WeightsControl
              onWeightsChange={handleWeightsChange}
              onReset={handleWeightsReset}
            />
            <RestaurantList
              restaurants={restaurants}
              loading={loading}
              error={error}
              onRestaurantClick={handleRestaurantClick}
            />
          </div>
        )}

        {currentStep === 'error' && (
          <div className="content-wrapper">
            <div className="error-state">
              <div className="error-content">
                <span className="error-icon-large">⚠️</span>
                <h2>추천 생성 실패</h2>
                <p>{error}</p>
                <button className="retry-button" onClick={handleRetry}>
                  처음부터 다시 시작
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {selectedRestaurant && (
        <RestaurantModal restaurant={selectedRestaurant} onClose={closeModal} />
      )}

      <footer className="app-footer">
        <p>&copy; 2025 길따라 맛따라. All rights reserved.</p>
      </footer>
    </div>
  );
}

export default App;
