package com.orderdelivery.deliveryservice.cache;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Optional;

/**
 * Cache-aside caching for a rider's availability flag
 * (key: rider:available:{riderId}). Shorter TTL than the order-status cache
 * (see OrderStatusCacheWriter in order-service / tracking-service) since
 * availability is more operationally dynamic.
 *
 * Deliberately NOT used by the rider-matching algorithm itself
 * (DeliveryService.assignRider always queries Postgres directly via
 * RiderRepository) — matching decisions need the current true state, and a
 * cache read there could assign to a rider whose availability just changed
 * elsewhere. This cache only serves read-heavy display/lookup paths
 * (GET /api/riders/{id}).
 *
 * Every method degrades to a no-op / cache-miss on any Redis exception —
 * Postgres is always the fallback, never a hard dependency on this cache.
 */
@Component
public class RiderAvailabilityCache {

    private static final Logger log = LoggerFactory.getLogger(RiderAvailabilityCache.class);
    static final String KEY_PREFIX = "rider:available:";
    static final Duration TTL = Duration.ofSeconds(60);

    private final StringRedisTemplate redisTemplate;

    public RiderAvailabilityCache(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public Optional<Boolean> get(Long riderId) {
        try {
            String value = redisTemplate.opsForValue().get(KEY_PREFIX + riderId);
            return value == null ? Optional.empty() : Optional.of(Boolean.parseBoolean(value));
        } catch (Exception e) {
            log.warn("Redis unavailable, falling back to Postgres for rider {} availability: {}", riderId, e.getMessage());
            return Optional.empty();
        }
    }

    public void put(Long riderId, boolean available) {
        try {
            redisTemplate.opsForValue().set(KEY_PREFIX + riderId, String.valueOf(available), TTL);
        } catch (Exception e) {
            log.warn("Redis unavailable, skipping cache write for rider {}: {}", riderId, e.getMessage());
        }
    }
}
