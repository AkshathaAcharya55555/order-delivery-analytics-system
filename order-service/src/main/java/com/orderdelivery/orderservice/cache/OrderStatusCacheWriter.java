package com.orderdelivery.orderservice.cache;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * Write-through updates to the shared "order status" Redis cache
 * (key: order:status:{orderId}) that tracking-service reads from. order-service
 * never reads this cache itself (its own GET returns the full order from
 * Postgres regardless) — it only keeps the cache in sync for the two
 * transitions it owns (PLACED, CANCELLED), same key namespace and TTL
 * tracking-service uses. See root README's Redis section for the full
 * rationale and what happens if Redis is down (every method here degrades
 * to a no-op on failure — Postgres remains the source of truth either way).
 */
@Component
public class OrderStatusCacheWriter {

    private static final Logger log = LoggerFactory.getLogger(OrderStatusCacheWriter.class);
    static final String KEY_PREFIX = "order:status:";
    static final Duration TTL = Duration.ofMinutes(10);

    private final StringRedisTemplate redisTemplate;

    public OrderStatusCacheWriter(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public void writeThrough(Long orderId, String status) {
        try {
            redisTemplate.opsForValue().set(KEY_PREFIX + orderId, status, TTL);
        } catch (Exception e) {
            log.warn("Redis unavailable, skipping cache write for order {}: {}", orderId, e.getMessage());
        }
    }
}
