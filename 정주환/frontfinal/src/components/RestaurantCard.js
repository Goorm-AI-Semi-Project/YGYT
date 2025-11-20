import React from 'react';
import { FaStar, FaMapMarkerAlt } from 'react-icons/fa';
import './RestaurantCard.css';

function RestaurantCard({ restaurant, onClick }) {
  // 디버깅: 받은 데이터 확인
  console.log('Restaurant data:', restaurant);
  console.log('Available keys:', Object.keys(restaurant));

  // 번역된 데이터가 있으면 사용, 없으면 원본 사용
  const name = restaurant.translatedName || restaurant.name || restaurant['식당명'] || 'Unknown';
  const cuisine_type = restaurant.translatedCuisine || restaurant.cuisine_type || restaurant.high_level_category || restaurant['음식종류'];
  const address = restaurant.translatedAddress || restaurant.address || restaurant['상세주소'] || restaurant['지역'];
  const rating = restaurant.rating || restaurant['평점'];
  const price_range = restaurant.price_range || restaurant.budget_range || restaurant['가격대'];
  const image_url = restaurant.image_url;
  const id = restaurant.id;

  // 주소에서 구/동만 추출 (간결하게)
  const getShortAddress = (fullAddress) => {
    if (!fullAddress) return '';
    const parts = fullAddress.split(' ');
    // "서울특별시 강남구 역삼동" -> "강남구 역삼동"
    if (parts.length >= 3) {
      return `${parts[1]} ${parts[2]}`;
    }
    return parts.slice(0, 2).join(' ');
  };

  // 이미지 URL이 없으면 음식 종류에 맞는 랜덤 음식 사진 사용
  const getImageUrl = () => {
    if (image_url && image_url !== 'N/A' && image_url.startsWith('http')) {
      return image_url;
    }

    // 음식 종류별 실제 Unsplash 사진 ID 배열
    const foodImages = {
      '한식': [
        'photo-1590301157890-4810ed352733', // 비빔밥
        'photo-1498654896293-37aacf113fd9', // 한식
        'photo-1569058242253-92a9c755a0ec', // 불고기
        'photo-1580870069867-74c57ee1bb07', // 김치찌개
      ],
      '중식': [
        'photo-1563245372-f21724e3856d', // 중식
        'photo-1526318896980-cf78c088247c', // 탕수육
        'photo-1582878826629-29b7ad1cdc43', // 짜장면
      ],
      '일식': [
        'photo-1579584425555-c3ce17fd4351', // 초밥
        'photo-1553621042-f6e147245754', // 라멘
        'photo-1617196034796-73dfa7b1fd56', // 일식
      ],
      '양식': [
        'photo-1546069901-ba9599a7e63c', // 스테이크
        'photo-1565299624946-b28f40a0ae38', // 피자
        'photo-1555939594-58d7cb561ad1', // 파스타
      ],
      '카페': [
        'photo-1509042239860-f550ce710b93', // 커피
        'photo-1495474472287-4d71bcdd2085', // 라떼
        'photo-1442512595331-e89e73853f31', // 카페
      ],
      '이탈리안': [
        'photo-1565299624946-b28f40a0ae38', // 피자
        'photo-1555939594-58d7cb561ad1', // 파스타
        'photo-1621996346565-e3dbc646d9a9', // 이탈리안
      ],
    };

    // 음식 종류에 맞는 이미지 배열 가져오기
    const images = foodImages[cuisine_type] || [
      'photo-1414235077428-338989a2e8c0', // 레스토랑
      'photo-1517248135467-4c7edcad34c4', // 레스토랑 내부
      'photo-1555939594-58d7cb561ad1', // 음식
    ];

    // id 기반으로 일관된 이미지 선택
    const seed = id ? id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) : 0;
    const selectedImage = images[seed % images.length];

    return `https://images.unsplash.com/${selectedImage}?w=600&h=400&fit=crop&q=80`;
  };

  return (
    <div className="restaurant-card" onClick={() => onClick && onClick(restaurant)}>
      <div className="card-image-wrapper">
        <img
          src={getImageUrl()}
          alt={name}
          className="card-image"
          onError={(e) => {
            // 이미지 로딩 실패시 대체 이미지
            e.target.style.display = 'none';
            e.target.parentElement.innerHTML = '<div class="card-image placeholder"><span>🍽️</span></div>';
          }}
        />

        {/* 이미지 위에 평점 오버레이 */}
        {rating && (
          <div className="rating-overlay">
            <FaStar className="star-icon" />
            <span className="rating-value">{rating.toFixed(1)}</span>
          </div>
        )}

        {/* 이미지 하단 그라데이션 오버레이 */}
        <div className="image-gradient"></div>
      </div>

      <div className="card-content">
        <h3 className="restaurant-name">{name}</h3>

        {address && (
          <p className="address">
            <FaMapMarkerAlt className="location-icon" />
            {getShortAddress(address)}
          </p>
        )}

        <div className="hashtags">
          {cuisine_type && (
            <span className="hashtag">#{cuisine_type}</span>
          )}
          {price_range && (
            <span className="hashtag">#{price_range}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default RestaurantCard;
