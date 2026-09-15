package com.orderdelivery.trackingservice.service;

import com.orderdelivery.trackingservice.cache.OrderStatusCache;
import com.orderdelivery.trackingservice.entity.Order;
import com.orderdelivery.trackingservice.entity.OrderStatusHistory;
import com.orderdelivery.trackingservice.event.EventPublisher;
import com.orderdelivery.trackingservice.exception.InvalidTransitionException;
import com.orderdelivery.trackingservice.exception.ResourceNotFoundException;
import com.orderdelivery.trackingservice.model.OrderStatus;
import com.orderdelivery.trackingservice.repository.OrderRepository;
import com.orderdelivery.trackingservice.repository.OrderStatusHistoryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TrackingServiceTest {

    @Mock private OrderRepository orderRepository;
    @Mock private OrderStatusHistoryRepository historyRepository;

    // Plain no-op subclasses rather than @Mock: Mockito's inline mock maker
    // cannot instrument concrete classes on Java 25 in this environment.
    private final OrderStatusCache orderStatusCache = new OrderStatusCache(null) {
        @Override
        public java.util.Optional<String> get(Long orderId) {
            return java.util.Optional.empty();
        }

        @Override
        public void put(Long orderId, String status) {
        }
    };
    private final EventPublisher eventPublisher = new EventPublisher(null, null) {
        @Override
        public void publishStatusChanged(Long orderId, java.util.Map<String, Object> payload) {
        }
    };

    private TrackingService trackingService;

    @BeforeEach
    void setUp() {
        trackingService = new TrackingService(orderRepository, historyRepository, orderStatusCache, eventPublisher);
    }

    private static Order orderWithStatus(Long id, OrderStatus status) throws Exception {
        Constructor<Order> ctor = Order.class.getDeclaredConstructor();
        ctor.setAccessible(true);
        Order order = ctor.newInstance();
        setField(order, "orderId", id);
        setField(order, "status", status);
        return order;
    }

    private static void setField(Object target, String name, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(target, value);
    }

    @Test
    void addTrackingEvent_legalTransition_updatesOrderAndAppendsHistory() throws Exception {
        Order order = orderWithStatus(1L, OrderStatus.PLACED);
        when(orderRepository.findById(1L)).thenReturn(Optional.of(order));
        when(historyRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        OrderStatusHistory result = trackingService.addTrackingEvent(1L, OrderStatus.CONFIRMED);

        assertThat(order.getStatus()).isEqualTo(OrderStatus.CONFIRMED);
        assertThat(result.getStatus()).isEqualTo(OrderStatus.CONFIRMED);
        verify(orderRepository).save(order);
    }

    @Test
    void addTrackingEvent_illegalTransition_throws() throws Exception {
        Order order = orderWithStatus(2L, OrderStatus.PLACED);
        when(orderRepository.findById(2L)).thenReturn(Optional.of(order));

        // PLACED cannot jump straight to PREPARING
        assertThatThrownBy(() -> trackingService.addTrackingEvent(2L, OrderStatus.PREPARING))
                .isInstanceOf(InvalidTransitionException.class);
        verify(historyRepository, never()).save(any());
    }

    @Test
    void addTrackingEvent_terminalOrder_rejectsAnyTransition() throws Exception {
        Order order = orderWithStatus(3L, OrderStatus.DELIVERED);
        when(orderRepository.findById(3L)).thenReturn(Optional.of(order));

        assertThatThrownBy(() -> trackingService.addTrackingEvent(3L, OrderStatus.CANCELLED))
                .isInstanceOf(InvalidTransitionException.class);
    }

    @Test
    void getOrder_missing_throwsNotFound() {
        when(orderRepository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> trackingService.getOrder(99L))
                .isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void fullHappyPathTransitionChain_isAllLegal() throws Exception {
        OrderStatus[] chain = {
                OrderStatus.PLACED, OrderStatus.CONFIRMED, OrderStatus.PREPARING,
                OrderStatus.READY_FOR_PICKUP, OrderStatus.RIDER_ASSIGNED, OrderStatus.PICKED_UP,
                OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED
        };
        for (int i = 0; i < chain.length - 1; i++) {
            assertThat(chain[i].canTransitionTo(chain[i + 1]))
                    .as("%s -> %s should be legal", chain[i], chain[i + 1])
                    .isTrue();
        }
    }
}
