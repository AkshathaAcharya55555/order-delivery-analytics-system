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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class TrackingService {

    private final OrderRepository orderRepository;
    private final OrderStatusHistoryRepository historyRepository;
    private final OrderStatusCache orderStatusCache;
    private final EventPublisher eventPublisher;

    public TrackingService(OrderRepository orderRepository, OrderStatusHistoryRepository historyRepository,
                            OrderStatusCache orderStatusCache, EventPublisher eventPublisher) {
        this.orderRepository = orderRepository;
        this.historyRepository = historyRepository;
        this.orderStatusCache = orderStatusCache;
        this.eventPublisher = eventPublisher;
    }

    @Transactional(readOnly = true)
    public Order getOrder(Long orderId) {
        return orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
    }

    /** Cache-aside read: served entirely from Redis on a hit, Postgres only on a miss. */
    @Transactional(readOnly = true)
    public String getCurrentStatus(Long orderId) {
        return orderStatusCache.get(orderId).orElseGet(() -> {
            String status = getOrder(orderId).getStatus().name();
            orderStatusCache.put(orderId, status);
            return status;
        });
    }

    @Transactional(readOnly = true)
    public List<OrderStatusHistory> getHistory(Long orderId) {
        return historyRepository.findByOrderIdOrderByChangedAtAsc(orderId);
    }

    /**
     * Records a new status transition for an order, validated against
     * OrderStatus's transition matrix. This is the only write path capable
     * of driving PLACED -> CONFIRMED -> PREPARING -> READY_FOR_PICKUP — the
     * stages order-service and delivery-service's own endpoints don't cover.
     */
    @Transactional
    public OrderStatusHistory addTrackingEvent(Long orderId, OrderStatus newStatus) {
        Order order = getOrder(orderId);

        if (!order.getStatus().canTransitionTo(newStatus)) {
            throw new InvalidTransitionException(
                    "Order " + orderId + " cannot move from " + order.getStatus() + " to " + newStatus);
        }

        OrderStatus previousStatus = order.getStatus();
        order.setStatus(newStatus);
        orderRepository.save(order);

        LocalDateTime now = LocalDateTime.now();
        OrderStatusHistory saved = historyRepository.save(new OrderStatusHistory(orderId, newStatus, now));

        orderStatusCache.put(orderId, newStatus.name());
        eventPublisher.publishStatusChanged(orderId, Map.of(
                "previous_status", previousStatus.name(),
                "new_status", newStatus.name()));

        return saved;
    }
}
