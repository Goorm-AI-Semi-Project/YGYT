import React, { useState, useEffect } from 'react';
import RestaurantCard from './RestaurantCard';
import { batchTranslateText } from '../services/api';
import './RestaurantList.css';

function RestaurantList({ restaurants, loading, error, onRestaurantClick, selectedLanguage = 'ko' }) {
  const [translatedRestaurants, setTranslatedRestaurants] = useState([]);
  const [translating, setTranslating] = useState(false);

  // 언어가 변경되거나 레스토랑 목록이 변경되면 배치 번역 실행
  useEffect(() => {
    const translateAllRestaurants = async () => {
      if (selectedLanguage === 'ko' || !restaurants || restaurants.length === 0) {
        setTranslatedRestaurants([]);
        return;
      }

      setTranslating(true);
      try {
        // 모든 레스토랑의 이름, 음식 종류, 주소를 수집
        const names = [];
        const cuisineTypes = [];
        const addresses = [];

        restaurants.forEach(restaurant => {
          const name = restaurant.name || restaurant['식당명'] || '';
          const cuisine = restaurant.cuisine_type || restaurant.high_level_category || restaurant['음식종류'] || '';
          const address = restaurant.address || restaurant['상세주소'] || restaurant['지역'] || '';

          names.push(name);
          cuisineTypes.push(cuisine);
          addresses.push(address);
        });

        // 모든 텍스트를 하나의 배열로 합치기
        const allTexts = [...names, ...cuisineTypes, ...addresses];

        // 배치 번역 실행
        const result = await batchTranslateText(allTexts, selectedLanguage);
        const translations = result.translations;

        // 번역 결과를 레스토랑별로 분리
        const restaurantCount = restaurants.length;
        const translatedData = restaurants.map((restaurant, index) => ({
          ...restaurant,
          translatedName: translations[index],
          translatedCuisine: translations[index + restaurantCount],
          translatedAddress: translations[index + restaurantCount * 2]
        }));

        setTranslatedRestaurants(translatedData);
      } catch (error) {
        console.error('배치 번역 실패:', error);
        setTranslatedRestaurants([]);
      } finally {
        setTranslating(false);
      }
    };

    translateAllRestaurants();
  }, [selectedLanguage, restaurants]);

  if (loading || translating) {
    return (
      <div className="restaurant-list-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>{translating ? '번역 중...' : '맛집을 찾는 중...'}</p>
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

  // 번역된 데이터가 있으면 사용, 없으면 원본 사용
  const displayRestaurants = translatedRestaurants.length > 0 ? translatedRestaurants : restaurants;

  return (
    <div className="restaurant-list-container">
      <div className="restaurant-grid">
        {displayRestaurants.map((restaurant, index) => (
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
