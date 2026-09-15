package com.orderdelivery.orderservice.service;

import com.orderdelivery.orderservice.cache.OrderStatusCacheWriter;
import com.orderdelivery.orderservice.dto.CreateOrderRequest;
import com.orderdelivery.orderservice.dto.OrderItemRequest;
import com.orderdelivery.orderservice.entity.Order;
import com.orderdelivery.orderservice.event.EventPublisher;
import com.orderdelivery.orderservice.exception.InvalidOrderStateException;
import com.orderdelivery.orderservice.exception.ResourceNotFoundException;
import com.orderdelivery.orderservice.model.OrderStatus;
import com.orderdelivery.orderservice.repository.CustomerRepository;
import com.orderdelivery.orderservice.repository.LocationRepository;
import com.orderdelivery.orderservice.repository.OrderRepository;
import com.orderdelivery.orderservice.repository.OrderStatusHistoryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    private OrderRepository orderRepository;
    @Mock
    private CustomerRepository customerRepository;
    @Mock
    private LocationRepository locationRepository;
    @Mock
    private OrderStatusHistoryRepository historyRepository;

    // Plain no-op subclasses rather than @Mock: Mockito's inline mock maker
    // cannot instrument concrete classes on Java 25 in this environment (see
    // delivery-service's DeliveryServiceTest for the same issue/fix).
    private final EventPublisher eventPublisher = new EventPublisher(null, null) {
        @Override
        public void publishOrderCreated(Long orderId, java.util.Map<String, Object> payload) {
        }

        @Override
        public void publishOrderCancelled(Long orderId, java.util.Map<String, Object> payload) {
        }
    };
    private final OrderStatusCacheWriter cacheWriter = new OrderStatusCacheWriter(null) {
        @Override
        public void writeThrough(Long orderId, String status) {
        }
    };

    private OrderService orderService;

    @BeforeEach
    void setUp() {
        orderService = new OrderService(orderRepository, customerRepository, locationRepository, historyRepository,
                eventPublisher, cacheWriter);
    }

    @Test
    void createOrder_computesTotalFromItems_andPersistsPlacedHistory() {
        when(customerRepository.existsById(1L)).thenReturn(true);
        when(locationRepository.existsById(1L)).thenReturn(true);
        when(orderRepository.save(any(Order.class))).thenAnswer(invocation -> invocation.getArgument(0));

        CreateOrderRequest request = new CreateOrderRequest();
        request.setCustomerId(1L);
        request.setDeliveryLocationId(1L);
        request.setPaymentMethod("card");

        OrderItemRequest item1 = new OrderItemRequest();
        item1.setProductName("Burger");
        item1.setCategory("main");
        item1.setUnitPrice(new BigDecimal("8.50"));
        item1.setQuantity(2);

        OrderItemRequest item2 = new OrderItemRequest();
        item2.setProductName("Soda");
        item2.setCategory("drink");
        item2.setUnitPrice(new BigDecimal("2.50"));
        item2.setQuantity(1);

        request.setItems(List.of(item1, item2));

        Order result = orderService.createOrder(request);

        assertThat(result.getStatus()).isEqualTo(OrderStatus.PLACED);
        assertThat(result.getTotalAmount()).isEqualByComparingTo("19.50"); // 2*8.50 + 1*2.50
        assertThat(result.getItems()).hasSize(2);

        ArgumentCaptor<com.orderdelivery.orderservice.entity.OrderStatusHistory> historyCaptor =
                ArgumentCaptor.forClass(com.orderdelivery.orderservice.entity.OrderStatusHistory.class);
        verify(historyRepository).save(historyCaptor.capture());
        assertThat(historyCaptor.getValue().getStatus()).isEqualTo(OrderStatus.PLACED);
    }

    @Test
    void createOrder_unknownCustomer_throwsNotFound() {
        when(customerRepository.existsById(999L)).thenReturn(false);

        CreateOrderRequest request = new CreateOrderRequest();
        request.setCustomerId(999L);
        request.setDeliveryLocationId(1L);
        request.setPaymentMethod("card");
        request.setItems(List.of());

        assertThatThrownBy(() -> orderService.createOrder(request))
                .isInstanceOf(ResourceNotFoundException.class);
        verifyNoInteractions(orderRepository);
    }

    @Test
    void cancelOrder_alreadyDelivered_throwsInvalidState() {
        Order delivered = new Order(1L, 1L, OrderStatus.DELIVERED, LocalDateTime.now(), BigDecimal.TEN, "card");
        when(orderRepository.findById(5L)).thenReturn(Optional.of(delivered));

        assertThatThrownBy(() -> orderService.cancelOrder(5L))
                .isInstanceOf(InvalidOrderStateException.class);
        verify(orderRepository, never()).save(any());
    }

    @Test
    void cancelOrder_fromPlaced_succeedsAndRecordsHistory() {
        Order placed = new Order(1L, 1L, OrderStatus.PLACED, LocalDateTime.now(), BigDecimal.TEN, "card");
        when(orderRepository.findById(7L)).thenReturn(Optional.of(placed));
        when(orderRepository.save(any(Order.class))).thenAnswer(invocation -> invocation.getArgument(0));

        Order result = orderService.cancelOrder(7L);

        assertThat(result.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        verify(historyRepository).save(any());
    }

    @Test
    void getOrder_missing_throwsNotFound() {
        when(orderRepository.findById(42L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> orderService.getOrder(42L))
                .isInstanceOf(ResourceNotFoundException.class);
    }
}
