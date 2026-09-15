package com.orderdelivery.trackingservice.cache;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Optional;

/**
 * Cache-aside + write-through caching for "frequently accessed order
 * status" (key: order:status:{orderId}). This is the same key namespace
 * order-service's OrderStatusCacheWriter writes to for the two transitions
 * it owns (PLACED, CANCELLED) — tracking-service is the primary reader and
 * keeps the cache current for every other transition, both via its own
 * addTrackingEvent() and via the Kafka consumer (EventConsumer) reacting to
 * other services' events. TTL is a safety net against a missed invalidation,
 * not the primary consistency mechanism (that's the write-through calls).
 *
 * Every method degrades to a cache-miss / no-op on a Redis exception —
 * Postgres (via TrackingService) is always the fallback, never a hard
 * dependency on this cache. See root README's Redis section.
 */
@Component
public class OrderStatusCache {

    private static final Logger log = LoggerFactory.getLogger(OrderStatusCache.class);
    static final String KEY_PREFIX = "order:status:";
    static final Duration TTL = Duration.ofMinutes(10);

    private final StringRedisTemplate redisTemplate;

    public OrderStatusCache(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public Optional<String> get(Long orderId) {
        try {
            return Optional.ofNullable(redisTemplate.opsForValue().get(KEY_PREFIX + orderId));
        } catch (Exception e) {
            log.warn("Redis unavailable, falling back to Postgres for order {} status: {}", orderId, e.getMessage());
            return Optional.empty();
        }
    }

    public void put(Long orderId, String status) {
        try {
            redisTemplate.opsForValue().set(KEY_PREFIX + orderId, status, TTL);
        } catch (Exception e) {
            log.warn("Redis unavailable, skipping cache write for order {}: {}", orderId, e.getMessage());
        }
    }
}
