import { useState, useEffect, useRef } from 'react';
import { FaBalanceScale, FaRoute, FaGlobe, FaStar, FaDollarSign } from 'react-icons/fa';
import { IoRefresh } from 'react-icons/io5';
import './WeightsControl.css';

function WeightsControl({ onWeightsChange, onReset }) {
  const [weights, setWeights] = useState({
    travel: 0.4,
    friendliness: 0.3,
    quality: 0.2,
    price: 0.1
  });

  const [isExpanded, setIsExpanded] = useState(false);
  const debounceTimerRef = useRef(null);

  const handleWeightChange = (key, value) => {
    const newWeight = parseFloat(value);
    const newWeights = { ...weights, [key]: newWeight };

    // 합이 1.0이 되도록 자동 조정
    const total = Object.values(newWeights).reduce((sum, w) => sum + w, 0);

    if (total > 0) {
      // 정규화: 모든 가중치를 합이 1.0이 되도록 비례 조정
      const normalized = {};
      Object.keys(newWeights).forEach(k => {
        normalized[k] = parseFloat((newWeights[k] / total).toFixed(2));
      });
      setWeights(normalized);

      // 디바운싱: 슬라이더 조절 멈춘 후 800ms 뒤에 API 요청
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        onWeightsChange(normalized);
      }, 800);
    }
  };

  // 컴포넌트 언마운트 시 타이머 정리
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const handleReset = () => {
    const defaultWeights = {
      travel: 0.4,
      friendliness: 0.3,
      quality: 0.2,
      price: 0.1
    };
    setWeights(defaultWeights);
    onWeightsChange(defaultWeights);
    if (onReset) onReset();
  };

  const weightConfigs = [
    {
      key: 'travel',
      label: '거리/이동',
      icon: <FaRoute />,
      description: '가까운 곳 우선',
      color: '#4A90E2'
    },
    {
      key: 'friendliness',
      label: '외국인 친화',
      icon: <FaGlobe />,
      description: '영어메뉴/소통 편의',
      color: '#7B68EE'
    },
    {
      key: 'quality',
      label: '평점/품질',
      icon: <FaStar />,
      description: '맛집 평가 우선',
      color: '#F5A623'
    },
    {
      key: 'price',
      label: '가격대',
      icon: <FaDollarSign />,
      description: '내 예산 맞춤',
      color: '#50C878'
    }
  ];

  return (
    <div className="weights-control">
      <button
        className="weights-toggle-button"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <FaBalanceScale className="toggle-icon" />
        <span>내 취향대로 추천받기</span>
        <span className={`arrow ${isExpanded ? 'expanded' : ''}`}>▼</span>
      </button>

      {isExpanded && (
        <div className="weights-panel">
          <div className="weights-header">
            <p>무엇이 가장 중요한가요? 슬라이더를 움직여 나만의 추천 기준을 설정하세요</p>
            <button className="reset-button" onClick={handleReset}>
              <IoRefresh />
              <span>기본값으로</span>
            </button>
          </div>

          <div className="weights-grid">
            {weightConfigs.map(config => (
              <div key={config.key} className="weight-item">
                <div className="weight-header">
                  <div className="weight-info">
                    <div className="weight-icon" style={{ color: config.color }}>
                      {config.icon}
                    </div>
                    <div className="weight-labels">
                      <label className="weight-label">{config.label}</label>
                      <span className="weight-description">{config.description}</span>
                    </div>
                  </div>
                  <span className="weight-value">{(weights[config.key] * 100).toFixed(0)}%</span>
                </div>

                <div className="slider-container">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weights[config.key]}
                    onChange={(e) => handleWeightChange(config.key, e.target.value)}
                    className="weight-slider"
                    style={{
                      background: `linear-gradient(to right, ${config.color} 0%, ${config.color} ${weights[config.key] * 100}%, #e0e0e0 ${weights[config.key] * 100}%, #e0e0e0 100%)`
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="weights-summary">
            <span className="summary-label">합계:</span>
            <span className="summary-value">
              {(Object.values(weights).reduce((sum, w) => sum + w, 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default WeightsControl;
