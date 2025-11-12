import React from 'react';
import RestaurantCard from './RestaurantCard';
import './RestaurantList.css';

function RestaurantList({ restaurants, loading, error, onRestaurantClick }) {
  if (loading) {
    return (
      <div className="restaurant-list-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>맛집을 찾는 중...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="restaurant-list-container">
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!restaurants || restaurants.length === 0) {
    return (
      <div className="restaurant-list-container">
        <div className="empty-state">
          <span className="empty-icon">🔍</span>
          <h3>검색 결과가 없습니다</h3>
          <p>다른 키워드로 검색해보세요</p>
        </div>
      </div>
    );
  }

  return (
    <div className="restaurant-list-container">
      <div className="restaurant-grid">
        {restaurants.map((restaurant, index) => (
          <RestaurantCard
            key={restaurant.id || index}
            restaurant={restaurant}
            onClick={onRestaurantClick}
          />
        ))}
      </div>
    </div>
  );
}

export default RestaurantList;
