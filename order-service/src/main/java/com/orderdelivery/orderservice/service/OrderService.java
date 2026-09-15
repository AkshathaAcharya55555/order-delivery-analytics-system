package com.orderdelivery.orderservice.service;

import com.orderdelivery.orderservice.cache.OrderStatusCacheWriter;
import com.orderdelivery.orderservice.dto.CreateOrderRequest;
import com.orderdelivery.orderservice.dto.OrderItemRequest;
import com.orderdelivery.orderservice.entity.Order;
import com.orderdelivery.orderservice.entity.OrderItem;
import com.orderdelivery.orderservice.entity.OrderStatusHistory;
import com.orderdelivery.orderservice.event.EventPublisher;
import com.orderdelivery.orderservice.exception.InvalidOrderStateException;
import com.orderdelivery.orderservice.exception.ResourceNotFoundException;
import com.orderdelivery.orderservice.model.OrderStatus;
import com.orderdelivery.orderservice.repository.CustomerRepository;
import com.orderdelivery.orderservice.repository.LocationRepository;
import com.orderdelivery.orderservice.repository.OrderRepository;
import com.orderdelivery.orderservice.repository.OrderStatusHistoryRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Map;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final CustomerRepository customerRepository;
    private final LocationRepository locationRepository;
    private final OrderStatusHistoryRepository historyRepository;
    private final EventPublisher eventPublisher;
    private final OrderStatusCacheWriter cacheWriter;

    public OrderService(OrderRepository orderRepository, CustomerRepository customerRepository,
                         LocationRepository locationRepository, OrderStatusHistoryRepository historyRepository,
                         EventPublisher eventPublisher, OrderStatusCacheWriter cacheWriter) {
        this.orderRepository = orderRepository;
        this.customerRepository = customerRepository;
        this.locationRepository = locationRepository;
        this.historyRepository = historyRepository;
        this.eventPublisher = eventPublisher;
        this.cacheWriter = cacheWriter;
    }

    @Transactional
    public Order createOrder(CreateOrderRequest request) {
        if (!customerRepository.existsById(request.getCustomerId())) {
            throw new ResourceNotFoundException("Customer not found: " + request.getCustomerId());
        }
        if (!locationRepository.existsById(request.getDeliveryLocationId())) {
            throw new ResourceNotFoundException("Location not found: " + request.getDeliveryLocationId());
        }

        LocalDateTime now = LocalDateTime.now();
        Order order = new Order(request.getCustomerId(), request.getDeliveryLocationId(),
                OrderStatus.PLACED, now, BigDecimal.ZERO, request.getPaymentMethod());

        BigDecimal total = BigDecimal.ZERO;
        for (OrderItemRequest itemRequest : request.getItems()) {
            OrderItem item = new OrderItem(itemRequest.getProductName(), itemRequest.getCategory(),
                    itemRequest.getUnitPrice(), itemRequest.getQuantity());
            order.addItem(item);
            total = total.add(item.computeLineTotal());
        }

        order.setTotalAmount(total);
        Order saved = orderRepository.save(order);
        historyRepository.save(new OrderStatusHistory(saved.getOrderId(), OrderStatus.PLACED, now));

        cacheWriter.writeThrough(saved.getOrderId(), OrderStatus.PLACED.name());
        eventPublisher.publishOrderCreated(saved.getOrderId(), Map.of(
                "customer_id", saved.getCustomerId(),
                "total_amount", saved.getTotalAmount()));

        return saved;
    }

    @Transactional(readOnly = true)
    public Order getOrder(Long orderId) {
        return orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
    }

    @Transactional(readOnly = true)
    public Page<Order> listOrders(OrderStatus status, Pageable pageable) {
        return status == null
                ? orderRepository.findAll(pageable)
                : orderRepository.findByStatus(status, pageable);
    }

    @Transactional
    public Order cancelOrder(Long orderId) {
        Order order = getOrder(orderId);
        if (!order.getStatus().canTransitionTo(OrderStatus.CANCELLED)) {
            throw new InvalidOrderStateException(
                    "Order " + orderId + " cannot be cancelled from status " + order.getStatus());
        }
        OrderStatus previousStatus = order.getStatus();
        order.setStatus(OrderStatus.CANCELLED);
        Order saved = orderRepository.save(order);
        historyRepository.save(new OrderStatusHistory(orderId, OrderStatus.CANCELLED, LocalDateTime.now()));

        cacheWriter.writeThrough(orderId, OrderStatus.CANCELLED.name());
        eventPublisher.publishOrderCancelled(orderId, Map.of("previous_status", previousStatus.name()));

        return saved;
    }
}
