import React, { useEffect, useState } from 'react';
import { getRestaurantDetail } from '../services/api';
import './RestaurantModal.css';

function RestaurantModal({ restaurant, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (restaurant && restaurant.id) {
      loadRestaurantDetail(restaurant.id);
    }
  }, [restaurant]);

  const loadRestaurantDetail = async (restaurantId) => {
    setLoading(true);
    try {
      const data = await getRestaurantDetail(restaurantId);
      setDetail(data);
    } catch (error) {
      console.error('상세 정보 로드 실패:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!restaurant) return null;

  const displayData = detail || restaurant;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          ✕
        </button>

        {loading ? (
          <div className="modal-loading">
            <div className="spinner"></div>
            <p>상세 정보를 불러오는 중...</p>
          </div>
        ) : (
          <>
            <div className="modal-header">
              {displayData.image_url && (
                <img
                  src={displayData.image_url}
                  alt={displayData.name}
                  className="modal-image"
                />
              )}
              <h2>{displayData.name}</h2>
              {displayData.rating && (
                <div className="modal-rating">
                  <span className="star">⭐</span>
                  <span>{displayData.rating.toFixed(1)}</span>
                </div>
              )}
            </div>

            <div className="modal-body">
              <div className="info-section">
                <h3>📍 위치</h3>
                <p>{displayData.address || '주소 정보 없음'}</p>
              </div>

              {displayData.cuisine_type && (
                <div className="info-section">
                  <h3>🍽️ 음식 종류</h3>
                  <p>{displayData.cuisine_type}</p>
                </div>
              )}

              {displayData.price_range && (
                <div className="info-section">
                  <h3>💰 가격대</h3>
                  <p>{displayData.price_range}</p>
                </div>
              )}

              {displayData.summary && (
                <div className="info-section">
                  <h3>📝 소개</h3>
                  <p>{displayData.summary}</p>
                </div>
              )}

              {displayData.menus && displayData.menus.length > 0 && (
                <div className="info-section">
                  <h3>🍴 메뉴</h3>
                  <div className="menu-list">
                    {displayData.menus.map((menu, index) => (
                      <div key={index} className="menu-item">
                        <span className="menu-name">
                          {menu.name}
                          {menu.is_representative === 'Y' && <span className="badge-representative"> 대표</span>}
                        </span>
                        {menu.price && (
                          <span className="menu-price">
                            {parseInt(menu.price).toLocaleString()}원
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default RestaurantModal;
