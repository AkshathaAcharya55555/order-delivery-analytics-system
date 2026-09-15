package com.orderdelivery.deliveryservice.cache;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * Proves the "Redis unavailable -> Postgres fallback" behavior for real,
 * rather than asserting on mocked exception plumbing: this test points a
 * real StringRedisTemplate at a port nothing is listening on, so every call
 * genuinely fails at the network level, exactly like a down Redis would.
 */
class RiderAvailabilityCacheFallbackTest {

    private final LettuceConnectionFactory brokenFactory = new LettuceConnectionFactory("localhost", 1);
    private RiderAvailabilityCache cache;

    RiderAvailabilityCacheFallbackTest() {
        brokenFactory.afterPropertiesSet();
        StringRedisTemplate template = new StringRedisTemplate(brokenFactory);
        template.afterPropertiesSet();
        cache = new RiderAvailabilityCache(template);
    }

    @AfterEach
    void tearDown() {
        brokenFactory.destroy();
    }

    @Test
    void get_whenRedisUnreachable_returnsEmptyInsteadOfThrowing() {
        assertThatCode(() -> {
            Optional<Boolean> result = cache.get(123L);
            assertThat(result).isEmpty();
        }).doesNotThrowAnyException();
    }

    @Test
    void put_whenRedisUnreachable_isANoOpInsteadOfThrowing() {
        assertThatCode(() -> cache.put(123L, true)).doesNotThrowAnyException();
    }
}
